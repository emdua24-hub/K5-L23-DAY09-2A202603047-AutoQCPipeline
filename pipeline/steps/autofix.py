"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _fx(image, line, action, before, after):
    return dict(image=image, line="" if line is None else line, action=action, before=before, after=after)


def _clip(text):
    """Cắt box về trong [0,1]. Trả về dòng mới, hoặc None nếu sau khi cắt box không còn diện tích."""
    c, x, y, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]          # cảnh báo là việc của người: không động tới
    fixes = []

    # 1) xoá ảnh (làm TRƯỚC để các issue dòng của ảnh đó được bỏ qua êm)
    removed = set()
    for i in errors:
        if i.code in REMOVE_CODES and i.image not in removed:
            removed.add(i.image)
            img = ds.image_path(i.image)
            if img is None:                                       # đã xoá ở lần chạy trước -> idempotent
                continue
            img.unlink()
            ds.label_path(i.image).unlink(missing_ok=True)
            fixes.append(_fx(i.image, None, "remove_image", img.name, f"đã xoá ({i.code})"))

    # 2) data.yaml: ghi lại names đúng danh sách dự án (một lần)
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        d = {}
        if ds.yaml_path.exists():
            d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        before = d.get("names")
        d["names"] = list(cfg["classes"])
        d["nc"] = len(cfg["classes"])
        ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append(_fx("data.yaml", None, "rename_classes", str(before), str(d["names"])))

    # 3) ảnh chưa có nhãn: KHÔNG tạo file (rỗng = "ảnh nền"), chỉ ghi lại để chuyển người gán
    needs = set()
    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed and i.image not in needs:
            needs.add(i.image)
            fixes.append(_fx(i.image, None, "needs_label", "(không có file)", "chuyển người gán"))

    # 4) lỗi theo dòng: gom theo file -> {số dòng GỐC: {mã lỗi}}, rồi ghi file MỘT lần
    by_file = defaultdict(lambda: defaultdict(set))
    for i in errors:
        if i.line is not None and i.code in DROP_CODES | CLIP_CODES and i.image not in removed:
            by_file[i.image][i.line].add(i.code)

    for stem, by_line in sorted(by_file.items()):
        path = ds.label_path(stem)
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8", errors="replace").splitlines()   # giữ cả dòng trống -> số dòng gốc
        kept = []
        for n, text in enumerate(original, 1):
            codes = by_line.get(n)
            if not codes:
                kept.append(text)
            elif codes & DROP_CODES:                              # xoá dòng thắng cắt box
                fixes.append(_fx(stem, n, "drop_line", text, f"(xoá: {', '.join(sorted(codes))})"))
            else:                                                 # chỉ BOX_OUT_OF_IMAGE
                try:
                    new = _clip(text)
                except ValueError:                                # issue cũ không khớp nội dung hiện tại: để yên
                    kept.append(text)
                    continue
                if new is None:
                    fixes.append(_fx(stem, n, "drop_line", text, "(xoá: box nằm hẳn ngoài ảnh)"))
                else:
                    kept.append(new)
                    fixes.append(_fx(stem, n, "clip_box", text, new))
        if kept != original:
            path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return fixes
