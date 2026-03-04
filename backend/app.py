
import uuid
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from openai import OpenAI

from dotenv import load_dotenv
import os
from corn import supabase
from flask import Response, stream_with_context
import json
from normalize import SINGLE_TOKEN_MAP, CONTEXT_RULES, BANNED_KEYWORDS, normalize_text, check_rewrite, AbbreviationResolver
from model import rewrite_query, detect_query, llm_answer, classify_llm, classify_subject_bo_may, classify_subject_QA, classify_subject_procedure
from system import apply_semantic_guard
from embedding import get_embedding
from utils import SUBJECT_KEYWORDS, classify, prepare_subject_keywords


PREPARED = prepare_subject_keywords(SUBJECT_KEYWORDS)

load_dotenv()

app = Flask(__name__)
CORS(app)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

resolver = AbbreviationResolver(SINGLE_TOKEN_MAP, CONTEXT_RULES)

@app.route('/api/get-chunks', methods=['GET'])
def get_chunks():
    try:
        response = supabase.table("documents") \
            .select("id, procedure_name, text_content, category, subject, is_active, effective_date") \
            .execute()

        if not response.data:
            return jsonify({
                "chunks": [],
                "message": "No chunks available"
            }), 200

        return jsonify({
            "chunks": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/api/get-alias', methods=['GET'])
def get_alias():
    try:
        response = supabase.table("alias") \
            .select("id, document_id, alias_text, normalized_alias") \
            .execute()

        if not response.data:
            return jsonify({
                "alias": [],
                "message": "No alias available"
            }), 200

        return jsonify({
            "alias": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/get-logs', methods=['GET'])
def get_logs():
    try:
        response = supabase.table("log_query") \
            .select("id, raw_query, expanded_query, answer, event_type, reason, alias_score, document_score, confidence_score, response_time_ms") \
            .execute()

        if not response.data:
            return jsonify({
                "logs": [],
                "message": "No alias available"
            }), 200

        return jsonify({
            "logs": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/delete-logs', methods=['GET'])
def delete_logs():
    try:
        response = supabase.table("log_query") \
            .select("id, raw_query, expanded_query, event_type, reason, alias_score, document_score, confidence_score, response_time_ms") \
            .execute()

        if not response.data:
            return jsonify({
                "logs": [],
                "message": "No alias available"
            }), 200

        return jsonify({
            "logs": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/create-chunk', methods=['POST'])
def create_chunk():
    try:
        data = request.json

        # Validate cơ bản
        if not data.get("text_content"):
            return jsonify({"error": "text_content is required"}), 400

        new_chunk = {
            "tenant_name": data.get("tenant_name") or 'xa_ba_diem',
            "scope": data.get("scope") or 'xa',
            "procedure_name": data.get("procedure_name") or None,
            "text_content": data.get("text_content") or '',
            "normalized_text": normalize_text(data.get("procedure_name")) if data.get("procedure_name") else normalize_text(data.get("text_content")),
            "category": data.get("category") or None,
            "subject": data.get("subject") or None,
            "embedding": get_embedding(data.get("text_content")) if data.get("text_content") else None
        }

        response = supabase.table("documents") \
            .insert(new_chunk) \
            .execute()

        return jsonify({
            "message": "Chunk created successfully",
            "data": response.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/create-alias', methods=['POST'])
def create_alias():
    try:
        data = request.json

        # Validate cơ bản
        if not data.get("alias_text"):
            return jsonify({"error": "alias_text is required"}), 400
        
        alias_embedding = client.embeddings.create(
            model="text-embedding-3-small",
            input=data.get("alias_text")
        ).data[0].embedding


        new_alias = {
            "document_id": data.get("document_id") or None,
            "alias_text": data.get("alias_text") or '',
            "normalized_alias": normalize_text(data.get("alias_text")) if data.get("alias_text") else '',
            "embedding": alias_embedding
        }

        response = supabase.table("alias") \
            .insert(new_alias) \
            .execute()

        return jsonify({
            "message": "Alias created successfully",
            "data": response.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def create_log(log_data):
    if log_data is None:
        return
    
    try:
        response = supabase.table("log_query") \
            .insert(log_data) \
            .execute()

        return jsonify({
            "message": "Log created successfully",
            "data": response.data
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-alias/<alias_id>', methods=['DELETE'])
def delete_alias(alias_id):
    try:
        response = supabase.table("alias") \
            .delete() \
            .eq("id", alias_id) \
            .execute()

        if not response.data:
            return jsonify({"error": "Alias not found"}), 404

        return jsonify({
            "message": "Alias deleted successfully"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update-chunk/<chunk_id>', methods=['PUT'])
def update_chunk(chunk_id):
    try:
        data = request.json

        text_content = data.get("text_content")

        response = supabase.table("documents") \
            .update({
                "text_content": data.get("text_content"),
                "normalized_text": normalize_text(text_content),
                "category": data.get("category") or None,
                "subject": data.get("subject") or None,
                "embedding": get_embedding(text_content)
            }) \
            .eq("id", chunk_id) \
            .execute()
        
        if not response.data:
            return jsonify({"error": "Chunk not found"}), 404

        return jsonify({
            "message": "Chunk updated successfully",
            "data": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/api/update-alias/<alias_id>', methods=['PUT'])
def update_alias(alias_id):
    try:
        data = request.json

        alias_embedding = client.embeddings.create(
            model="text-embedding-3-small",
            input=data.get("alias_text")
        ).data[0].embedding

        response = supabase.table("alias") \
            .update({
                "document_id": data.get("document_id") or None,
                "alias_text": data.get("alias_text") or '',
                "normalized_alias": normalize_text(data.get("alias_text")) or '',
                "embedding": alias_embedding
            }) \
            .eq("id", alias_id) \
            .execute()
        
        if not response.data:
            return jsonify({"error": "Alias not found"}), 404

        return jsonify({
            "message": "Alias updated successfully",
            "data": response.data
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route("/api/load-history", methods=["POST"])
def load_history():

    data = request.json
    session_id = data.get("session_id")

    logs = (
        supabase
        .table("log_query")
        .select("raw_query, answer")
        .eq("session_chat", session_id)
        .eq("event_type", "normal")
        .order("created_at")
        .execute()
    )

    return jsonify({
        "logs": logs.data
    })

@app.route('/api/clear-session', methods=['POST'])
def clear_session():

    return jsonify({"message": "Session cleared"})

@app.route('/api/chat-stream', methods=['POST'])
def chat_stream():

    def generate():

        # ✅ LẤY DATA TRƯỚC
        data = request.json
        session_id = data.get("session_id")
        print("Session:", session_id)
        user_message = data.get('message', '').strip()
        origin_mess = user_message
        use_llm = data.get('use_llm', False)
        chunk_generate = data.get("chunk_limit", 1)
        log_data = {}

        session_history = (
            supabase
            .table("log_query")
            .select("expanded_query, answer")
            .eq("session_chat", session_id)
            .eq("event_type", "normal")
            .order("created_at", desc=True)
            .limit(2)
            .execute()
        )

        history_data = session_history.data

        re_check = False

        out_of_score_content = "Nội dung anh/chị hỏi nằm ngoài phạm vi hỗ trợ của hệ thống.\nAnh/chị vui lòng liên hệ đơn vị phù hợp hoặc đặt câu hỏi liên quan đến thủ tục hành chính để được hỗ trợ."
        complaint_content = "Thông tin của phán ánh sẽ được chuyển đến bộ phận chuyên môn để rà soát và cải thiện chất lượng phục vụ.\nCảm ơn anh/chị đã đóng góp ý kiến!"

        start = time.perf_counter()

        yield f"data: {json.dumps({'log': f'Nhận message...'})}\n\n"
        yield f"data: {json.dumps({'log': f'Kiểm tra viết tắt'})}\n\n"
        result = resolver.process(user_message)
        user_message = result["expanded"]
        normalized_query = result["normalized"]
        yield f"data: {json.dumps({'log': f'{result}'})}\n\n"
        # normalized_query = normalize_text(q)
        yield f"data: {json.dumps({'log': f'Kiểm tra blacklist'})}\n\n"
        # 1️⃣ So nguyên dấu
        matched_keyword = next(
            (
                kw for kw in BANNED_KEYWORDS
                if kw.lower() in user_message.lower()
                or normalize_text(kw) in normalized_query
            ),
            None
        )

        if matched_keyword:
            end = time.perf_counter()
            duration = (end - start) * 1000 
            log_data["raw_query"] = user_message
            log_data["expanded_query"] = normalized_query
            log_data["event_type"] = "banned_topic"
            log_data["reason"]= f"Nội dung có chứa từ khóa cấm => {matched_keyword}"
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            create_log(log_data)
            yield f"data: {json.dumps({'log': f'[Blocked] Query: {user_message} => keyword: {matched_keyword}'})}\n\n"
            yield f"data: {json.dumps({'replies': out_of_score_content, 'chunks': []})}\n\n"
            return 

        query_embedding = get_embedding(user_message)

        print(history_data)

        if len(history_data) >= 1:
            yield f"data: {json.dumps({'log': f'Kiểm tra lịch sử hội thoại'})}\n\n"

            # last_answer = history_data[0]["answer"]
            # print(f"Câu trả lời trước: {last_answer}")
            last_question = history_data[0]["expanded_query"]
            print(f"Câu hỏi trước: {last_question}")
            # last_a_emb = session_history[-1]["embedding"]

            # check_question = check_rewrite(
            #     user_message,
            #     query_embedding,
            #     last_a_emb
            # )

            # if check_question:
            user_message = rewrite_query(user_message, last_question)
            query_embedding = get_embedding(user_message)
            normalized_query = normalize_text(user_message)

            yield f"data: {json.dumps({'log': f'Câu hỏi hoàn chỉnh: {user_message}'})}\n\n"


        yield f"data: {json.dumps({'log': f'Normalized: {normalized_query}'})}\n\n"

        category, subject = classify(normalized_query, PREPARED)
        yield f"data: {json.dumps({'log': f'Category: {category}, Subject: {subject}'})}\n\n"

        if category is None:
            re_check = True 
            category, subject = classify_llm(user_message)
            yield f"data: {json.dumps({'log': f'Sử dụng LLM để trích xuất => Category: {category}, Subject: {subject}'})}\n\n"

        if subject is None and category == "thu_tuc_hanh_chinh":
            subject = classify_subject_procedure(user_message, category)
            yield f"data: {json.dumps({'log': f'Sử dụng LLM để trích xuất => Category: {category}, Subject: {subject}'})}\n\n"
        
        if subject is None and category == "thong_tin_tong_quan":
            subject = classify_subject_QA(user_message, category)
            yield f"data: {json.dumps({'log': f'Sử dụng LLM để trích xuất => Category: {category}, Subject: {subject}'})}\n\n"
        
        if subject is None and category == "to_chuc_bo_may":
            re_check = True 
            subject = classify_subject_bo_may(user_message, category)

            yield f"data: {json.dumps({'log': f'Sử dụng LLM để trích xuất => Category: {category}, Subject: {subject}'})}\n\n"
        response = supabase.rpc(
            "search_documents_full_hybrid_v5",
            {
                "p_query_format": normalized_query,
                "p_query_embedding": query_embedding,
                "p_tenant": "xa_ba_diem",
                "p_category": category,
                "p_subject": subject,
                "p_limit": 12
            }
        ).execute()


        chunks = response.data or []
        

        if re_check:
            best_score = chunks[0]["confidence_score"] if chunks else 0
            if best_score < 0.3:
                response_all = supabase.rpc(
                    "search_documents_full_hybrid_v5",
                    {
                        "p_query_format": normalized_query,
                        "p_query_embedding": query_embedding,
                        "p_tenant": "xa_ba_diem",
                        "p_category": category,
                        "p_subject": None,
                        "p_limit": 5
                    }
                ).execute()

                chunks_all = response_all.data or []
                best_score_all = chunks_all[0]["confidence_score"] if chunks_all else 0

                # Nếu không subject tốt hơn → dùng nó
                if best_score_all > best_score:
                    chunks = chunks_all

        # if category == "thu_tuc_hanh_chinh" and subject:
        #     best_score = chunks[0]["confidence_score"] if chunks else 0
        #     if best_score < 0.3:
        #         response_all = supabase.rpc(
        #             "search_documents_full_hybrid_v5",
        #             {
        #                 "p_query_format": normalized_query,
        #                 "p_query_embedding": query_embedding,
        #                 "p_tenant": "xa_ba_diem",
        #                 "p_category": category,
        #                 "p_subject": None,
        #                 "p_limit": 12
        #             }
        #         ).execute()

        #         chunks_all = response_all.data or []
        #         best_score_all = chunks_all[0]["confidence_score"] if chunks_all else 0

        #         # Nếu không subject tốt hơn → dùng nó
        #         if best_score_all > best_score:
        #             chunks = chunks_all

        # Cắt top 5
        chunks = chunks[:5]
        if subject == "thong_tin_lien_he":
            score = chunks[0]["confidence_score"]
            if score < 0.5:
                # subject = "lanh_dao"
                response = supabase.rpc(
                    "search_documents_full_hybrid_v5",
                    {
                        "p_query_format": normalized_query,
                        "p_query_embedding": query_embedding,
                        "p_tenant": "xa_ba_diem",
                        "p_category": category,
                        "p_subject": None,
                        "p_limit": 5
                    }
                ).execute()
                chunks_temp = response.data

                if not chunks_temp:
                    return
                score_temp = chunks_temp[0]["confidence_score"]
                if score_temp > score:
                    chunks = chunks_temp
        


        if category == "thu_tuc_hanh_chinh":
            chunks = apply_semantic_guard(normalized_query ,chunks)[:5]
        
        # LOW_THRESHOLD = 0.25
        HIGH_THRESHOLD = 0.4
        score = chunks[0]["confidence_score"] if chunks else 0
        context = f"### Tài liệu\n{chunks[0]['text_content']}"
        if chunk_generate > 1:
            context = "\n\n".join(
                f"### Tài liệu {i+1}\n{chunk['text_content']}"
                for i, chunk in enumerate(chunks[:chunk_generate])
            )
        print(context)

        if score > HIGH_THRESHOLD:
            yield f"data: {json.dumps({'log': f'=> Được trả lời'})}\n\n"
            answer = "\n\n".join(
                f"Sử dụng các tài liệu sau:\n### Tài liệu {i+1}\n{chunk['text_content']}"
                for i, chunk in enumerate(chunks[:chunk_generate])
            )
    
            if use_llm:
                answer = llm_answer(user_message, context)

            end = time.perf_counter()
            duration = (end - start) * 1000 
            log_data["tenant_name"]= 'xa_ba_diem'
            log_data["raw_query"] = origin_mess
            log_data["expanded_query"] = user_message
            log_data["answer"]= answer
            log_data["detected_category"]= category
            log_data["detected_subject"]= subject
            log_data["event_type"] = "normal"
            log_data["alias_score"]= chunks[0]["alias_score"]
            log_data["document_score"]= chunks[0]["document_score"]
            log_data["confidence_score"]= chunks[0]["alias_score"]
            log_data["session_chat"]= session_id
            log_data["response_time_ms"]= round(duration / 1000,2)
            create_log(log_data)
            yield f"data: {json.dumps({'replies': answer, 'chunks': chunks})}\n\n"

            return

        # elif score < LOW_THRESHOLD:
        #     session_history.clear()
        #     end = time.perf_counter()
        #     duration = (end - start) * 1000 
        #     log_data["raw_query"] = user_message
        #     log_data["expanded_query"] = normalized_query
        #     log_data["event_type"] = "out_of_scope"
        #     log_data["reason"]= f"Điểm score thấp: {score}"
        #     log_data["alias_score"]= chunks[0]["alias_score"]
        #     log_data["document_score"]= chunks[0]["document_score"]
        #     log_data["confidence_score"]= chunks[0]["confidence_score"]
        #     log_data["response_time_ms"]= round(duration / 1000,2)
        #     create_log(log_data)
        #     yield f"data: {json.dumps({'replies': out_of_score_content, 'chunks': []})}\n\n"
        #     return
        
        elif score <= HIGH_THRESHOLD:
            yield f"data: {json.dumps({'log': f'Sử dụng LLM kiểm tra phạm vi câu hỏi: {user_message}'})}\n\n"
            flow_query = detect_query(user_message)
            if flow_query in ["qa", "complaint", "out_of_scope"]:
                if flow_query == "qa":
                    yield f"data: {json.dumps({'log': f'=> Được trả lời'})}\n\n"
                    answer = "\n\n".join(
                        f"Sử dụng các tài liệu sau:\n### Tài liệu {i+1}\n{chunk['text_content']}"
                        for i, chunk in enumerate(chunks[:chunk_generate])
                    )
                    if use_llm:
                        answer = llm_answer(user_message, context)

                    end = time.perf_counter()
                    duration = (end - start) * 1000 
                    log_data["tenant_name"]= 'xa_ba_diem'
                    log_data["raw_query"] = origin_mess
                    log_data["expanded_query"] = user_message
                    log_data["answer"]= answer
                    log_data["detected_category"]= category
                    log_data["detected_subject"]= subject
                    log_data["event_type"] = "normal"
                    log_data["alias_score"]= chunks[0]["alias_score"]
                    log_data["document_score"]= chunks[0]["document_score"]
                    log_data["confidence_score"]= chunks[0]["alias_score"]
                    log_data["session_chat"]= session_id
                    log_data["response_time_ms"]= round(duration / 1000,2)
                    create_log(log_data)
                    yield f"data: {json.dumps({'replies': answer, 'chunks': chunks})}\n\n"
                if flow_query == "complaint":
                    end = time.perf_counter()
                    duration = (end - start) * 1000 
                    log_data["tenant_name"]= 'xa_ba_diem'
                    log_data["raw_query"] = origin_mess
                    log_data["expanded_query"] = user_message
                    log_data["event_type"] = "complaint"
                    log_data["reason"]= f"Nội dung thuộc chủ đề góp ý, phàn nàn"
                    log_data["session_chat"]= session_id
                    log_data["response_time_ms"]= round(duration / 1000,2)
                    create_log(log_data)
                    yield f"data: {json.dumps({'log': f'=> Phản hồi góp ý'})}\n\n"

                    yield f"data: {json.dumps({'replies': complaint_content, 'chunks': []})}\n\n"
                if flow_query == "banned":
                    yield f"data: {json.dumps({'log': f'=> Ngoài phạm vi'})}\n\n"

                    end = time.perf_counter()
                    duration = (end - start) * 1000 
                    log_data["tenant_name"]= 'xa_ba_diem'
                    log_data["raw_query"] = origin_mess
                    log_data["expanded_query"] = user_message
                    log_data["event_type"] = "out_of_scope"
                    log_data["reason"]= f"LLM xác định => Chủ đề cấm không được trả lời"
                    log_data["session_chat"]= session_id
                    log_data["response_time_ms"]= round(duration / 1000,2)
                    create_log(log_data)
                    yield f"data: {json.dumps({'replies': out_of_score_content, 'chunks': []})}\n\n"
            return
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # cực quan trọng nếu có nginx
        }
    )

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Receive user message and return relevant responses
    Request: {"message": "user message"}
    Response: {"replies": [{"content": "...", "score": 0.95}, ...]}
    """
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    q_format = normalize_text(user_message)
    category, subject = classify(q_format)
    print(f"Query: {q_format}\n=> Category: {category}, Subject: {subject}\n")

    log_data = f"""Query: {user_message}\n=> Category: {category}, Subject: {subject}"""

    query_embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=user_message
    ).data[0].embedding

    response = supabase.rpc(
        "search_documents_full_hybrid_v4",
        {
            "p_query_format": q_format,
            "p_query_embedding": query_embedding,
            "p_tenant": "xa_ba_diem",
            "p_category": category,
            "p_subject": subject,
            "p_limit": 5
        }
    ).execute()

    # Return all responses from knowledge base (you can add better matching logic here)
    return jsonify({
        "replies": response.data,
        "message": user_message,
        "log_data":log_data,
        "timestamp": datetime.now().isoformat()
    })



@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True)
