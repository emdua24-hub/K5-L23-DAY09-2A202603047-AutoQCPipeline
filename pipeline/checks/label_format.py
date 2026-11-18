"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


NAME = "label_format"


def run(ds, cfg):
    p = cfg["label_format"]
    tol, min_px, max_frac, dup_iou = p["overflow_tol"], p["min_box_px"], p["max_box_frac"], p["dup_box_iou"]
    n_cls = len(ds.classes)
    issues = []
    for lab in ds.label_files():
        stem = lab.stem
        size = ds.image_size(stem) if ds.image_path(stem) else None   # nhãn mồ côi: không có ảnh -> bỏ qua BOX_TINY
        seen = []                                                     # (dòng, box) hợp lệ trước đó, để bắt DUP_BOX
        for ln_no, text in ds.read_label_lines(stem) or []:           # read_label_lines bỏ dòng trống, giữ số dòng gốc
            def add(sev, code, msg, **extra):
                issues.append(Issue(NAME, sev, code, stem, msg, ln_no, extra))

            try:
                c, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", f"dòng sai định dạng ({e}): {text.strip()!r}")
                continue
            if not 0 <= c < n_cls:
                add(ERROR, "BAD_CLASS_ID", f"id lớp {c} ngoài 0..{n_cls - 1}")
                continue
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", f"box rộng/cao bằng 0 (w={w}, h={h})")
                continue

            # mức tràn lớn nhất trong 4 mép (âm = nằm trong ảnh)
            overflow = max(0 - (x - w / 2), (x + w / 2) - 1, 0 - (y - h / 2), (y + h / 2) - 1)
            if overflow > tol:
                add(ERROR, "BOX_OUT_OF_IMAGE", f"box tràn ra ngoài ảnh {overflow:.4f}", overflow=round(overflow, 6))

            box = (x, y, w, h)
            for prev_ln, prev_c, prev_box in seen:
                if prev_c == c and iou_xywh(prev_box, box) > dup_iou:
                    add(ERROR, "DUP_BOX", f"trùng box dòng {prev_ln} (cùng lớp {c})", dup_of=prev_ln)
                    break
            seen.append((ln_no, c, box))

            if size:
                short_px = min(w * size[0], h * size[1])
                if short_px < min_px:
                    add(WARN, "BOX_TINY", f"cạnh ngắn {short_px:.1f}px < {min_px}px", short_px=round(short_px, 1))
            if w * h > max_frac:
                add(WARN, "BOX_HUGE", f"box phủ {w * h:.0%} ảnh", area=round(w * h, 4))
    return issues
