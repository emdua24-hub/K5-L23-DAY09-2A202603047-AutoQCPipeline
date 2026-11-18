# Báo cáo Day 09 — Đặng Thu Hương, 2A202603047

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát 10). Vào **224** ảnh raw; cửa vào loại **22** ảnh; **202** ảnh được xuất ra `export/clean_v1` dưới dạng **bản NHÁP** (`manifest.json` ghi `decision: Hold`), chưa phải bản phát hành.
Lý do: không còn lỗi bắt buộc (0 ERROR ở `07_error_list_v3`), nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa được người duyệt, vượt ngưỡng 10%. Hàng đợi duyệt có 125 ảnh mà ngân sách chỉ 80 ảnh.

## 2. Lỗi và phân việc
Số liệu từ `02_error_list_v1` (cửa vào: `01_intake`), dạng *số issue / số ảnh*.

| Mã lỗi | Số issue / ảnh | Ai sửa | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 / 8 | máy (loại ở cửa vào) | md5 trùng từng byte: chắc chắn |
| `DUP_IMAGE_NEAR` | 4 / 4 | máy (loại ở cửa vào) | phash ≤ 12, đã soi bằng mắt từng cặp (mục 3) |
| `LEAK_TEST` | 5 / 5 | máy (loại ở cửa vào) | trùng ảnh test/val: giữ lại thì metric đẹp giả |
| `CORRUPT_IMAGE`, `BAD_SIZE` | 2 / 2, 3 / 3 | máy (loại ở cửa vào) | không mở được / cạnh ngắn < 250 px |
| `BAD_FORMAT`, `BAD_CLASS_ID`, `BOX_ZERO`, `DUP_BOX` | 3, 6, 4, 7 dòng | máy (`drop_line`, 20 dòng) | dòng hỏng không thể đoán lại ý người gán: xoá an toàn hơn sửa |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy (`clip_box`, 8 dòng) | chỉ cắt phần tràn, giữ nguyên lớp |
| `BAD_CLASS_NAME` | 2 issue / `data.yaml` | máy (`rename_classes`) | tên lớp là quy tắc dự án cố định |
| `MISSING_LABEL_FILE` | 6 / 6 | **người** (`needs_label`) | máy không được bịa nhãn; file rỗng nghĩa là "ảnh nền", khác "chưa gán" |
| `POSSIBLE_MISSING` | 53 / 52 | **người** | model lớn thấy vật mà nhãn không có: cần mắt người xác nhận |
| `POSSIBLE_WRONG_CLASS` | 18 / 18 | **người** | nhầm lớp hợp lệ (xe tải ↔ bus) không bắt được bằng quy tắc |
| `POSSIBLE_LOOSE_BOX` | 28 / 24 | **người** | box lệch so với model; model cũng có thể lệch |
| `POSSIBLE_FALSE_POS` | 29 / 27 | **người** | box không khớp vật nào model thấy |
| `EMPTY_LABEL`, `BOX_TINY`, `BOX_HUGE`, `CLASS_RARE` | 12, 6, 3, 4 | **người** | có thể đúng (ảnh nền, vật ở xa) hoặc sai: chỉ người phân biệt được |

Hàng đợi `05_review_queue.csv` xếp theo tổng trọng số `review.weights`. Đầu hàng là `img_0020` (11,5: `FIXED_DROP_LINE` + `POSSIBLE_MISSING` + `POSSIBLE_WRONG_CLASS`). Tiếp theo là 5 ảnh `NEEDS_LABEL` (trọng số 10): ảnh chưa có nhãn mà không ai gán thì cả lô bị Rework, nên phải xem trước. Với ngân sách 80 ảnh, người duyệt xem được **74/103** ảnh có cờ ngữ nghĩa (`POSSIBLE_*`). Sau duyệt, cờ ngữ nghĩa giảm: `POSSIBLE_MISSING` 52 → 12 ảnh, `POSSIBLE_WRONG_CLASS` 18 → 3, `POSSIBLE_LOOSE_BOX` 24 → 20, `POSSIBLE_FALSE_POS` 27 → 21.

## 3. Calibration (2 ngưỡng)
Precision / Recall trên bộ calib (39 ảnh, `calibration_report.md`).

| Tham số | Khởi đầu | Đã chọn | P / R (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | `DUP_IMAGE_NEAR` 1.00 / 0.50 → 1.00 / 0.67 | Trên lô raw, 10–14 cho kết quả ổn định (4 near-dup, 5 leak). Giá trị 16 có F1 calib cao nhất (0.91) nhưng là ngưỡng nguy hiểm (xem dưới). Chọn giữa vùng ổn định để có biên an toàn hai phía. |
| `second_opinion.conf` | 0.25 | **0.6** | `MISSING` 0.50 / 1.00 → 0.57 / 1.00; `WRONG_CLASS` 0.56 / 0.83 → 0.62 / 0.83; `LOOSE_BOX` 0.29 / 0.40 → 0.20 / 0.20 | Tăng precision mà **giữ recall `MISSING` = 1.00**. Giá trị 0.8 cho F1 tổng cao hơn và làm pipeline ra Release (7,9% ảnh còn cảnh báo), nhưng recall `MISSING` tụt còn 0.75: một phần tư box thiếu lọt qua. Đổi phủ lỗi lấy "Release" là sai mục đích. Cái giá phải chấp nhận: recall `LOOSE_BOX` giảm còn 0.20. |

**Calibration có thể đánh lừa:** trên calib, `phash_dist = 16` là tốt nhất (recall `DUP_IMAGE_NEAR` 0.83). Chạy trên raw thì từ 14 lên 16, số near-dup tăng 4 → 7 và `LEAK_TEST` tăng 5 → 11; ở 20 có 105 `LEAK_TEST`. Soi bằng mắt 3 cặp mới ở dist 16: `img_0011`/`img_0008` (tennis và trượt tuyết) và `img_0177`/`img_0113` (lướt sóng và người ngồi bàn) là **ảnh khác hẳn nhau**. Chỉ `img_0084`/`img_0074` là trùng thật (cắt khung). Calib chỉ có 6 near-dup nên không thấy được tỉ lệ báo nhầm này. Theo F1 calib, pipeline sẽ xoá nhầm ảnh tốt.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt) cho kết quả: `REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE)`, **mã thoát 20**, log `KHÔNG xuất: còn lỗi bắt buộc`, thư mục `work/exp_nb` không được tạo. Khi có người duyệt 80 ảnh, 6 ảnh này được gán nhãn và lỗi bắt buộc về 0; khi đó gate mới xét đến tỉ lệ cảnh báo.

**(b) Điểm mù (có bằng chứng).**
1. **Thiếu người nhỏ trong ảnh đông.** Tự xem `img_0030`: thiếu 1 người bên phải (sau người 12), 1 người giữa người 13 và 17, và 1 người sau người 4. Máy chỉ báo **1** `POSSIBLE_MISSING` (conf 0,69, box rất nhỏ). Các người còn lại dưới `conf = 0.6` hoặc dưới `min_area_px = 600`, nên lọt.
2. **Box chỉ lộ một phần vật.** `img_0030` có 2 box ở rìa trái chỉ lộ một ít chân, không nhận ra là người. Máy cờ được 1 box (`POSSIBLE_FALSE_POS` dòng 9), nhưng trước đó `autofix` đã **cắt** đúng box này (`BOX_OUT_OF_IMAGE` → `clip_box`). Máy sửa cú pháp cho một box mà về ý nghĩa có lẽ nên xoá: autofix không biết box đó đáng giữ hay không.
3. **Near-dup biến đổi mạnh.** `img_0084`/`img_0074` (cắt khung, dist 16) lọt qua với `phash_dist = 12`: hai ảnh gần như cùng cảnh vẫn nằm trong dataset.
4. **Box lỏng nhẹ.** Recall `POSSIBLE_LOOSE_BOX` trên calib chỉ 0,20 ở `conf = 0.6`: phần lớn box lỏng không bị cờ.

Ghi nhận thêm, máy và người khớp nhau ở `img_0001`: tự xem thấy thiếu 1 người bên phải; máy báo `POSSIBLE_MISSING` (person, conf 0,95) đúng vị trí, và còn bắt thêm 1 `DUP_BOX` (dòng 3 trùng dòng 1) mà mắt thường khó thấy.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Colab T4, `yolo26n.pt`, 20 epoch, batch 16, imgsz 640, seed 0 và 1; cùng val (`gold_val`, 40 ảnh) và test (100 ảnh). `raw` train trên 224 ảnh, `clean` trên 202 ảnh (`clean_v1`, bản nháp Hold). Ở ô train, Ultralytics báo `raw` có 224 ảnh nhưng chỉ **218 file nhãn**. 6 ảnh thiếu nhãn khớp đúng 6 lỗi `MISSING_LABEL_FILE` mà pipeline đã bắt; Ultralytics coi chúng là ảnh nền, tức `raw` học rằng 6 ảnh có vật thể là "không có vật". Kết quả trong `submission/results/comparison.md`:

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

Chênh mAP50 (clean − raw) = **−0.025**, bằng đúng độ lệch giữa 2 seed của `clean` (0.025). Từng seed: `clean` 0.718 / 0.683, `raw` 0.726 / 0.726. Seed 0 của `clean` chỉ kém `raw` 0.008. Độ lệch của `raw` gần 0 chỉ là trùng hợp: precision của `raw` vẫn dao động ±0.061 giữa 2 seed.

**Kết luận trung thực:** với 2 seed và 100 ảnh test, chênh lệch **nằm trong nhiễu**. Thí nghiệm **không** cho thấy `clean` tốt hơn `raw`, và cũng không đủ để nói `clean` kém hơn. Phần lớn chênh lệch đến từ lớp `truck`: AP50 0.59 / 0.49 ở `clean` so với 0.66 / 0.64 ở `raw`. Riêng `clean` đã dao động 0.10 giữa 2 seed, trong khi `truck` chỉ có 41 box.

**Giả thuyết và cách kiểm:**
1. **`raw` được thổi phồng nhờ rò rỉ test.** Pipeline phát hiện 5 ảnh `LEAK_TEST` trong raw (`01_intake`): model `raw` đã thấy chúng lúc train. Cách kiểm: đo lại mAP trên test sau khi bỏ 5 ảnh test bị trùng (theo cột `extra.of` của `01_intake.csv`). Nếu `raw` tụt mà `clean` giữ nguyên thì chênh lệch là do rò rỉ.
2. **`clean` có ít dữ liệu hơn và vẫn còn nhãn sai.** `clean` có ít hơn 22 ảnh (loại 8 trùng tuyệt đối, 4 gần trùng, 5 rò rỉ, 5 hỏng/nhỏ). Ngoài ra còn 38 ảnh có cảnh báo chưa được người duyệt (Hold), và 20 dòng bị `drop_line`: vật trong những dòng đó thành "không có nhãn", nên model bị dạy rằng đó là nền. Cách kiểm: train thêm biến thể `oracle` (cùng ảnh với `clean`, nhãn người) làm chặn trên. Nếu `oracle` vượt `raw` rõ rệt thì vấn đề nằm ở phần nhãn chưa duyệt chứ không phải ở việc loại ảnh.
3. **Nhiễu thống kê.** Chỉ có 2 seed và 100 ảnh test, nên AP từng lớp dao động tới 0.10. Cách kiểm: tăng lên ≥ 5 seed và báo cáo khoảng tin cậy trước khi kết luận.

## 6. Quyết định và ghi chú AI
**(a) Quyết định:** giữ **Hold**. `clean_v1` chỉ dùng thử nghiệm, chưa phát hành. Để thành Release, người duyệt cần xử lý thêm ít nhất 18 trong 38 ảnh còn cảnh báo (để còn < 10% của 202 ảnh, tức ≤ 20 ảnh), ưu tiên theo `05_review_queue.csv`. Không đạt Release bằng cách nâng `conf` lên 0,8: cách đó chỉ làm máy im lặng hơn, không làm nhãn sạch hơn.

**(b) Ghi chú AI** (dùng Claude Code):
- *Prompt chính:* yêu cầu cùng làm lab, làm từng bước theo guidline và giải thích chi tiết code, tuân thủ các rule trong repo; AI đọc docstring và test của từng module (đầu vào, đầu ra, mã lỗi, ngưỡng lấy từ `cfg`), viết theo TDD từng module, mỗi module một commit.
- *Cách kiểm:* chạy `pytest` (79/79 xanh); đọc và hỏi lại từng khối code; chạy `make run`; đối chiếu `02_error_list_v1` với ảnh vẽ nhãn (`img_0001`, `img_0030`); soi bằng mắt các cặp ảnh trùng khi calibrate.
- *Một lần AI sai/thừa:* bản đầu của `autofix` có điều kiện thừa `len(kept) != len(original) or kept != original`, đã rút gọn. Ở `gate`, cách so `n >= 0.1 * n_images` cho kết quả sai ở biên (0,1 × 30 = 3,0000000000000004), phải so bằng tỉ lệ đã làm tròn.
