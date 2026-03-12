## Plan: Stabilize Classification And Evaluation Pipeline

Chuẩn hóa pipeline theo taxonomy thực tế của chunk để loại bỏ drift nhãn, tách rõ interaction intent khỏi retrieval taxonomy, và xây dựng bộ đánh giá phản ánh đúng chất lượng hệ thống thay vì bị nhiễu bởi log/debug cũ.

**Mục tiêu cốt lõi**
- Dùng chung một taxonomy contract cho runtime + evaluator.
- Tách interaction lane khỏi retrieval lane.
- Chặn nhãn ngoài taxonomy trước khi gọi retrieval.
- Đánh giá theo nhiều scoreboard đúng bản chất thay vì một điểm tổng.
- Thiết lập vòng cải tiến dài hạn từ log sạch, tránh hard-code theo case lẻ.

**Steps**
1. Phase 1 - Baseline And Taxonomy Contract
1.1. Chốt taxonomy retrieval từ chunk active (category + subject hợp lệ theo category).
1.2. Version hóa taxonomy thành schema dùng chung cho runtime + evaluator.
1.3. Định nghĩa output contract: `interaction_intent` tách biệt với `retrieval_category/retrieval_subject`.
1.4. Định nghĩa mapping nhãn sai: `invalid category -> None`, `invalid subject -> None`, kèm reason để log.
1.5. Ban hành rule vận hành: interaction-only query không bắt buộc expected retrieval label.

2. Phase 2 - Runtime Hardening (Long-term, non-hardcode)
2.1. Thêm taxonomy guard ngay sau rule/LLM classify, trước retrieval RPC.
2.2. Chuẩn hóa đầu ra `classify_llm` qua lớp `normalize_and_validate_labels`.
2.3. Tách nhánh interaction intent (greeting/complaint/help/clarification) khỏi retrieval flow.
2.4. Xử lý multi-intent bằng primary/secondary intent: primary route retrieval, secondary bổ sung phản hồi.
2.5. Giảm heuristic theo case lẻ; ưu tiên confidence gate + taxonomy validation + intent decomposition.
*depends on: phase 1*

3. Phase 3 - Evaluation Redesign (Correctness-first)
3.1. Tách bộ test: `retrieval_regression`, `interaction_regression`, `challenge_robustness`.
3.2. Tách scoreboard: retrieval accuracy, interaction accuracy, robustness pass rate.
3.3. Retest phải validate expected labels theo taxonomy trước khi chấm.
3.4. Case invalid expected label phải report là dataset issue, không trừ điểm model.
3.5. Thêm quality metrics: invalid-label count, short-query ratio, clarification-needed ratio.
3.6. Thiết lập ngưỡng release riêng cho từng scoreboard.
*depends on: phase 1*

4. Phase 4 - Data Pipeline And Continuous Improvement
4.1. Làm sạch log nguồn (lọc debug/noise, gắn cờ low-information).
4.2. Tách interaction-only queries trước khi sinh expected retrieval labels.
4.3. Chọn mẫu cân bằng theo category/subject/risk_type.
4.4. Chống trùng ngữ nghĩa bằng fingerprint + near-duplicate filter.
4.5. Thiết lập active-learning loop từ mismatch production theo cụm lỗi/tần suất/tác động.
4.6. Refresh taxonomy định kỳ từ chunk active + compatibility check data/prompt/runtime.
4.7. Định nghĩa SLA cải tiến: cấm patch hard-code 1 case ngoài contract.
*depends on: phase 2 and phase 3*

5. Phase 5 - Rollout And Risk Control
5.1. Rollout qua feature flag cho taxonomy guard + interaction split.
5.2. Theo dõi metrics production: fallback rate, invalid-label rate, clarification rate, retrieval hit quality, drop-off sau query ngắn.
5.3. Mở rộng rollout theo tenant/traffic khi đạt ngưỡng verification.
5.4. Dừng rollout khi có regression nghiêm trọng ở high-risk buckets.
*depends on: phase 2, phase 3, phase 4*

**Chi tiết Multi-intent: Cách thức thực hiện**
- Mục tiêu: khi câu hỏi chứa 2 ý trở lên, hệ thống không chọn sai 1 ý duy nhất mà phải tách ý, ưu tiên ý chính để retrieval, sau đó xử lý ý phụ.
- Ví dụ multi-intent thường gặp:
- `cho em xin sdt chi Thu va can giay to gi` (to_chuc_bo_may + thu_tuc_hanh_chinh)
- `chu tich ubnd xa la ai va bao lau co ket qua` (to_chuc_bo_may + thu_tuc_hanh_chinh)
- `ban giup gi dc cho toi va nop o dau` (interaction + thu_tuc_hanh_chinh)

1. Thiết kế output contract cho bộ phân tích intent
1.1. Trả về danh sách intents thay vì 1 nhãn duy nhất:
```json
{
	"intents": [
		{
			"type": "retrieval",
			"category": "to_chuc_bo_may",
			"subject": "nhan_su",
			"confidence": 0.84,
			"span": "cho em xin sdt chi thu"
		},
		{
			"type": "retrieval",
			"category": "thu_tuc_hanh_chinh",
			"subject": null,
			"confidence": 0.62,
			"span": "can giay to gi"
		}
	],
	"primary_intent_index": 0,
	"has_conflict": true
}
```
1.2. Giữ backward compatibility: nếu chỉ có 1 intent thì map ngược về `category/subject` như hiện tại.

2. Quy trình tách multi-intent (intent decomposition)
2.1. Tách câu theo connectors: `va`, `voi`, `roi`, `sau do`, `kem`, `dong thoi`, `?`.
2.2. Với mỗi mảnh câu, chạy classify riêng (rule-first, LLM fallback).
2.3. Gộp các intent cùng category nếu khác biệt nhỏ về subject/confidence.
2.4. Nếu có interaction + retrieval cùng lúc: interaction là secondary, retrieval là primary.
2.5. Nếu có 2 retrieval intents cạnh tranh: chọn primary theo score tổng hợp.

3. Cách chọn primary intent (tránh hard-code case lẻ)
3.1. Tính `priority_score` theo công thức tổng quát:
- `priority_score = w_confidence * confidence + w_specificity * specificity + w_retrieval_need * retrieval_need`
3.2. `specificity` cao hơn khi có subject hợp lệ theo taxonomy và query span đủ thông tin.
3.3. `retrieval_need` cao hơn khi intent yêu cầu tìm chunk để trả lời.
3.4. Nếu điểm 2 intent quá gần nhau (delta < threshold): trả lời primary + hỏi làm rõ ý secondary.

4. Routing và synthesis response
4.1. Chỉ gọi retrieval chính cho primary intent để tránh nhiễu chunk.
4.2. Secondary intent xử lý theo 2 kiểu:
- Nếu secondary là interaction: thêm câu giao tiếp ở đầu/cuối câu trả lời.
- Nếu secondary là retrieval và đủ tín hiệu: gọi retrieval nhẹ (top_k thấp) hoặc trả prompt hỏi rõ hơn.
4.3. Hợp nhất phản hồi theo template 2 phần:
- Phần A: trả lời ý chính (có nguồn chunk)
- Phần B: gợi ý/đặt câu hỏi cho ý phụ

5. Guardrails bắt buộc
5.1. Mọi label của từng intent phải đi qua taxonomy guard trước khi retrieval.
5.2. Intent có label invalid -> hạ xuống `category=None, subject=None` + flag `invalid_label`.
5.3. Nếu tất cả intents đều low-confidence -> trả `qa_need_info` thay vì đoán.

6. Logging và quan sát để cải tiến dài hạn
6.1. Log thêm trường:
- `is_multi_intent`
- `intent_count`
- `primary_intent`
- `secondary_intents`
- `decomposition_method` (rule/llm/hybrid)
6.2. Theo dõi metric mới:
- `multi_intent_detect_rate`
- `primary_intent_accuracy`
- `secondary_handled_rate`
- `multi_intent_fallback_rate`
6.3. Định kỳ gom lỗi multi-intent theo pattern để cập nhật rule tổng quát, không vá từng câu.

7. Kế hoạch triển khai theo code hiện tại
7.1. `backend/test_demo.py`
- Bổ sung hàm `decompose_intents(q_norm)` và `rank_intents(intents)`.
- `classify_v2` giữ output cũ, thêm output mở rộng `intents` khi bật feature flag.
7.2. `backend/app.py`
- Sau classify, nếu `is_multi_intent=True`: route theo primary intent.
- Chỉ gọi RPC retrieval theo nhãn primary đã qua taxonomy guard.
- Hợp nhất response theo 2 phần chính/phụ.
7.3. `backend/model.py`
- Cập nhật prompt LLM để trả được nhiều intents có `span` + `confidence`.
- Ép strict output format để parser ổn định.
7.4. `retest_classification.py`
- Thêm tập test `multi_intent_regression`.
- Chấm riêng `primary_correct` và `secondary_handled`.

8. Tiêu chí hoàn thành (Definition of Done)
8.1. Multi-intent benchmark đạt ngưỡng mục tiêu (ví dụ > 80% primary intent accuracy).
8.2. Không tăng invalid-label rate sau khi bật multi-intent pipeline.
8.3. Không tăng crash/error ở nhánh fallback LLM.
8.4. Có dashboard theo dõi metric multi-intent trong production.

**So sánh trước và sau (target state)**
- Trước: benchmark gộp nhiều loại case vào một điểm tổng.
- Sau: benchmark tách retrieval/interaction/robustness với score độc lập.
- Trước: classifier có thể trả nhãn ngoài taxonomy chunk và vẫn đi retrieval.
- Sau: mọi nhãn đi qua taxonomy guard; nhãn invalid bị chặn/chuẩn hóa trước RPC.
- Trước: interaction query bị trộn với retrieval query làm sai đánh giá.
- Sau: interaction và retrieval là 2 lane độc lập, metric và flow xử lý riêng.
- Trước: test data từ log cũ/debug dễ nhiễu, có expected label không hợp lệ.
- Sau: có data quality gate + taxonomy validation cho expected labels.
- Trước: fix lỗi theo case cụ thể, dễ hard-code và khó bảo trì.
- Sau: kiến trúc contract-based + guardrail hệ thống, giảm patch ad-hoc.

**Tác dụng theo từng phase**
1. Phase 1: thống nhất ngôn ngữ nhãn toàn hệ thống, giảm mismatch do định nghĩa khác nhau.
2. Phase 2: giảm lỗi runtime do nhãn sai/ngoài taxonomy, tăng ổn định ở nhánh fallback LLM.
3. Phase 3: đo đúng bài toán, tránh tối ưu nhầm mục tiêu do metric tổng bị nhiễu.
4. Phase 4: nâng chất lượng dữ liệu dài hạn, cải tiến bền vững thay vì vá ngắn hạn.
5. Phase 5: giảm rủi ro production, hỗ trợ rollback nhanh và quan sát tác động theo từng lớp traffic.

**Relevant files**
- `/var/www/chatbot_v2/backend/app.py`
- `/var/www/chatbot_v2/backend/test_demo.py`
- `/var/www/chatbot_v2/backend/model.py`
- `/var/www/chatbot_v2/backend/normalize.py`
- `/var/www/chatbot_v2/retest_classification.py`
- `/var/www/chatbot_v2/custom_test_questions_v1.json`
- `/var/www/chatbot_v2/retest_results_custom_retest_20260311_155656.json`
- `/var/www/chatbot_v2/backend/FLOW_BACKEND.md`

**Verification**
1. Chạy retrieval benchmark trên taxonomy-valid set và báo số case invalid expected labels.
2. Chạy interaction benchmark riêng, xác nhận không ép interaction vào retrieval taxonomy.
3. Chạy robustness benchmark theo risk bucket `short/abbr/multi/ambiguous`.
4. Kiểm tra logs xác nhận `invalid_label_guard` hoạt động.
5. Replay log sạch trước rollout rộng để kiểm tra regression.
6. Xác nhận không tăng crash/error rate khi bật guard (đặc biệt nhánh `need_llm=True`).

**Pre-test Checklist (Gate bắt buộc trước khi chạy benchmark)**
1. Chốt contract chấm interaction: dùng `interaction_intent` làm nhãn chấm chính, `event_type` làm nhãn vận hành/logging.
2. Chốt bảng mapping `interaction_intent <-> event_type` (ít nhất cho `chao_hoi`, `phan_nan`, `qa_need_info`, `out_of_scope`) và thống nhất cho runtime + evaluator.
3. Chốt rule chấm multi-intent: định nghĩa rõ `primary_correct`, `secondary_handled`, `multi_intent_fallback_rate`.
4. Đóng băng taxonomy retrieval từ chunk active và version hóa (ví dụ `taxonomy.v1.json`).
5. Validate toàn bộ expected labels của test suites theo taxonomy hiện hành; case invalid phải gắn `dataset_issue` và loại khỏi điểm model.
6. Xác nhận test suites đã tách lane: `retrieval_regression`, `interaction_regression`, `multi_intent_regression`, `challenge_robustness`.
7. Xác nhận feature flags ở trạng thái test an toàn (`ENABLE_TAXONOMY_GUARD`, `ENABLE_MULTI_INTENT`, `ENABLE_METADATA_ASSIST`) và có phương án rollback nhanh.
8. Xác nhận logging đã có các trường tối thiểu: `invalid_label_guard_triggered`, `label_before_guard`, `label_after_guard`, `is_multi_intent`, `primary_intent`, `secondary_intents`.
9. Chạy dry-run nhỏ (10-30 case/bucket) để kiểm tra parser evaluator không bị lệch định dạng SSE/log.
10. Chốt công thức KPI vận hành trước test chính thức: `wrong_confident_answer_rate`, `user_drop_off_rate`, cửa sổ đo và nguồn dữ liệu.

**Exit Criteria Cho Pre-test Checklist**
1. Không còn lỗi contract giữa runtime và evaluator.
2. Invalid expected labels đã được tách khỏi điểm model (report riêng `dataset_issue`).
3. Có báo cáo dry-run xác nhận parser + scoreboard hoạt động đúng lane.

**Decisions**
- In scope: chuẩn hóa taxonomy, tách interaction khỏi retrieval, tái thiết kế benchmark, vòng cải tiến từ log sạch.
- Out of scope: đổi kiến trúc nền vector DB/RPC hoặc fine-tune model nền.
- Assumption: taxonomy từ chunk active là source of truth cho retrieval labels.
- Assumption: interaction intent vẫn cần cho UX nhưng không dùng để chấm retrieval accuracy.

**Execution Plan Chi Tiết (6 tuần)**

1. Tuần 1 - Taxonomy Contract + Baseline đóng băng
1.1. Chốt taxonomy retrieval từ chunk active và xuất file contract versioned (`taxonomy.v1.json`).
1.2. Định nghĩa schema chuẩn cho output classify:
- `interaction_intent`
- `intents[]`
- `primary_intent_index`
- `retrieval_category`
- `retrieval_subject`
1.3. Bổ sung validator dùng chung cho runtime và evaluator.
1.4. Chạy baseline benchmark hiện tại, lưu snapshot metrics làm mốc so sánh.
1.5. Deliverables:
- `docs/taxonomy_contract.md`
- `backend/taxonomy_contract.json`
- báo cáo baseline score (retrieval/interaction/robustness).
1.6. Acceptance criteria:
- 100% nhãn trong benchmark được check hợp lệ theo contract.
- Không còn chỗ nào tự định nghĩa nhãn rời rạc ngoài contract.

2. Tuần 2 - Runtime Guardrails (không thay đổi behavior lớn)
2.1. Thêm `normalize_and_validate_labels()` vào flow classify.
2.2. Chặn nhãn invalid trước RPC retrieval.
2.3. Bổ sung flag log:
- `invalid_label_guard_triggered`
- `label_before_guard`
- `label_after_guard`
2.4. Bật feature flag `ENABLE_TAXONOMY_GUARD=false` mặc định, test ở staging trước.
2.5. Deliverables:
- patch `backend/app.py`
- patch `backend/model.py`
- dashboard mini theo dõi invalid-label rate.
2.6. Acceptance criteria:
- Invalid label sent to RPC = 0.
- Không tăng lỗi 5xx so với baseline.

3. Tuần 3 - Multi-intent Decomposition (core)
3.1. Xây `decompose_intents(q_norm)` (rule/hybrid).
3.2. Xây `rank_intents(intents)` để chọn primary intent theo score tổng quát.
3.3. Cập nhật response synthesis 2 phần:
- phần chính theo primary
- phần phụ cho secondary
3.4. Bổ sung fallback khi confidence gần nhau (ask clarifying question).
3.5. Feature flag `ENABLE_MULTI_INTENT=false` mặc định.
3.6. Deliverables:
- patch `backend/test_demo.py`
- patch `backend/app.py`
- tài liệu `docs/multi_intent_design.md`.
3.7. Acceptance criteria:
- Chạy được end-to-end với multi-intent queries mẫu.
- Không phá backward compatibility single-intent.

4. Tuần 4 - Evaluation Redesign + Test Suites
4.1. Tách data test thành:
- `retrieval_regression.json`
- `interaction_regression.json`
- `multi_intent_regression.json`
- `challenge_robustness.json`
4.2. Nâng cấp `retest_classification.py` để xuất multi-scoreboard.
4.3. Thêm kiểm tra `dataset_issue` khi expected label invalid.
4.4. Deliverables:
- 4 file test suite mới
- script retest mới
- mẫu báo cáo `reports/retest_summary_template.md`.
4.5. Acceptance criteria:
- Có báo cáo tách riêng 4 scoreboard.
- Không còn trừ điểm model vì expected label invalid.

5. Tuần 5 - Log Pipeline + Active Learning Loop
5.1. Làm sạch log nguồn trước khi sinh case:
- lọc debug/noise
- gắn cờ low-information
- tách interaction-only.
5.2. Cluster mismatch theo pattern lỗi (`short`, `abbr`, `multi`, `ambiguous`).
5.3. Tạo vòng review hàng tuần: top 20 mismatch ảnh hưởng cao.
5.4. Deliverables:
- script `tools/clean_logs_for_eval.py`
- script `tools/cluster_mismatch.py`
- báo cáo tuần `reports/mismatch_weekly.md`.
5.5. Acceptance criteria:
- Tỷ lệ case trùng/ngẫu nhiên giảm rõ (theo chỉ số dedup).
- Có backlog lỗi ưu tiên tự động theo tần suất x tác động.

6. Tuần 6 - Rollout có kiểm soát + ổn định production
6.1. Bật dần feature flags theo traffic:
- 10% -> 30% -> 60% -> 100%.
6.2. Theo dõi các SLO chính:
- invalid-label rate
- fallback rate
- primary intent accuracy
- error rate 5xx
- user drop-off.
6.3. Thiết lập tiêu chí rollback tự động.
6.4. Deliverables:
- runbook rollout/rollback
- dashboard production metrics
- post-rollout report.
6.5. Acceptance criteria:
- Không regression nghiêm trọng ở high-risk bucket.
- Đạt ngưỡng mục tiêu trên scoreboard đã định.

**Workstreams song song (gợi ý phân người)**
- Stream A (Runtime): `backend/app.py`, `backend/model.py`, flags, guardrails.
- Stream B (Classification): `backend/test_demo.py`, multi-intent decomposition/ranking.
- Stream C (Evaluation): `retest_classification.py`, dataset split, reporting.
- Stream D (DataOps): clean log pipeline, mismatch clustering, weekly review.

**KPI mục tiêu sau rollout**
- Invalid label to RPC: 0.
- Retrieval taxonomy-valid accuracy: +8% đến +12% so với baseline.
- Multi-intent primary accuracy: >= 80%.
- Short-query wrong confident answer: giảm >= 40%.
- 5xx error rate: không tăng so với baseline.

**Rủi ro và phương án giảm thiểu**
- Rủi ro: rule decomposition tạo over-split intent.
- Giảm thiểu: threshold merge + fallback clarification khi confidence sát nhau.
- Rủi ro: đánh đổi tốc độ do pipeline dài hơn.
- Giảm thiểu: chỉ retrieval sâu cho primary intent; secondary dùng lightweight path.
- Rủi ro: drift taxonomy khi chunk cập nhật.
- Giảm thiểu: compatibility check tự động mỗi lần refresh chunk.
