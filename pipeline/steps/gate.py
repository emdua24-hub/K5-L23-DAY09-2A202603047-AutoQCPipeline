"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    reviewed = set(reviewed)
    threshold = cfg["gate"]["warn_ratio_hold"]

    # lỗi bắt buộc: đếm TẤT CẢ (kể cả cấp dataset như data.yaml), không bao giờ bỏ qua vì đã duyệt
    errors = [i for i in issues if i.severity == ERROR]
    # cảnh báo: đếm số ẢNH khác nhau, chỉ ảnh còn trong dataset và chưa được người duyệt
    warn_images = {i.image for i in issues if i.severity == WARN and i.image in stems and i.image not in reviewed}

    n_images = len(stems)
    warn_ratio = round(len(warn_images) / n_images, 4) if n_images else 0.0   # tránh chia cho 0
    # so bằng tỉ lệ đã làm tròn: 3/30 phải ra đúng 0.1 (n >= 0.1*30 sẽ sai vì 0.1*30 = 3.0000000000000004)

    if errors:
        codes = sorted({i.code for i in errors})
        decision = "Rework"
        reasons = [f"còn {len(errors)} lỗi bắt buộc ({', '.join(codes)}) -> trả về sửa, không phát hành"]
    elif warn_ratio >= threshold:
        decision = "Hold"
        reasons = [f"{len(warn_images)}/{n_images} ảnh ({warn_ratio:.1%}) còn cảnh báo chưa người duyệt "
                   f">= ngưỡng {threshold:.0%} -> tạm giữ"]
    else:
        decision = "Release"
        reasons = [f"không còn lỗi bắt buộc; {len(warn_images)}/{n_images} ảnh ({warn_ratio:.1%}) còn cảnh báo "
                   f"< ngưỡng {threshold:.0%} -> phát hành"]

    return dict(decision=decision, n_errors=len(errors), n_warn_images=len(warn_images),
                n_images=n_images, warn_ratio=warn_ratio, reasons=reasons)
