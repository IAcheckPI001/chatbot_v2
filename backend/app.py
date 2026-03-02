
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from openai import OpenAI

from dotenv import load_dotenv
import os
from utils import normalize_text, classify
from corn import supabase

load_dotenv()

app = Flask(__name__)
CORS(app)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


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

        category = data.get("category")
        text_content = data.get("text_content")

        if category == "thong_tin_phuong":
            normalized_text = normalize_text(text_content)

        response = supabase.table("documents") \
            .update({
                "text_content": data.get("text_content"),
                "normalized_text": normalized_text,
                "category": data.get("category") or None,
                "subject": data.get("subject") or None
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

from flask import Response, stream_with_context
import json
from normalize import SINGLE_TOKEN_MAP, BANNED_KEYWORDS, expand_abbreviations, expand_context_sensitive, check_rewrite
from model import rewrite_query, detect_query, llm_answer
from system import apply_semantic_guard
from embedding import get_embedding

session_history = []

@app.route('/api/chat-stream', methods=['POST'])
def chat_stream():

    # ✅ LẤY DATA TRƯỚC
    data = request.json
    user_message = data.get('message', '').strip()

    def generate():

        yield f"data: {json.dumps({'log': f'Nhận message...'})}\n\n"
        yield f"data: {json.dumps({'log': f'Kiểm tra viết tắt'})}\n\n"
        q = expand_context_sensitive(user_message)
        q = expand_abbreviations(q, SINGLE_TOKEN_MAP)
        yield f"data: {json.dumps({'log': f'Câu hỏi hiện tại: {q}'})}\n\n"
        normalized_query = normalize_text(q)
        yield f"data: {json.dumps({'log': f'Kiểm tra blacklist'})}\n\n"
        # 1️⃣ So nguyên dấu
        matched_keyword = next(
            (
                kw for kw in BANNED_KEYWORDS
                if kw.lower() in q.lower()
                or normalize_text(kw) in normalized_query
            ),
            None
        )

        if matched_keyword:
            yield f"data: {json.dumps({'log': f'[Blocked] Query: {q} => keyword: {matched_keyword}'})}\n\n"
            return 

        query_embedding = get_embedding(q)

        if len(session_history) >= 2:
            yield f"data: {json.dumps({'log': f'Kiểm tra lịch sử hội thoại'})}\n\n"
            last_question = session_history[-2]["text"]
            last_answer = session_history[-1]["text"]
            last_a_emb = session_history[-1]["embedding"]

            check_question = check_rewrite(normalized_query, query_embedding, last_a_emb)
            if check_question:
                q = rewrite_query(q, last_question, last_answer)
                query_embedding = get_embedding(q)
                normalized_query = normalize_text(q)
                yield f"data: {json.dumps({'log': f'Câu hỏi hoàn chỉnh: {q}'})}\n\n"

        session_history.append({
            "text": q,
            "embedding": None
        })
        yield f"data: {json.dumps({'log': f'Normalized: {normalized_query}'})}\n\n"

        category, subject = classify(normalized_query)
        yield f"data: {json.dumps({'log': f'Category: {category}, Subject: {subject}'})}\n\n"

        response = supabase.rpc(
            "search_documents_full_hybrid_v4",
            {
                "p_query_format": normalized_query,
                "p_query_embedding": query_embedding,
                "p_tenant": "xa_ba_diem",
                "p_category": category,
                "p_subject": subject,
                "p_limit": 5
            }
        ).execute()

        chunks = response.data

        if not chunks:
            return
        
        chunks = chunks[:5]

        if category == "thu_tuc_hanh_chinh":
            chunks = apply_semantic_guard(normalized_query ,chunks)[:5]
        
        LOW_THRESHOLD = 0.27
        HIGH_THRESHOLD = 0.5
        score = chunks[0]["score"] if chunks else 0
        context = f"### Tài liệu\n{chunks[0]['text_content']}"

        out_of_score_content = "Nội dung anh/chị hỏi nằm ngoài phạm vi hỗ trợ của hệ thống.\nAnh/chị vui lòng liên hệ đơn vị phù hợp hoặc đặt câu hỏi liên quan đến thủ tục hành chính để được hỗ trợ."
        complaint_content = "Thông tin của phán ánh sẽ được chuyển đến bộ phận chuyên môn để rà soát và cải thiện chất lượng phục vụ.\nCảm ơn anh/chị đã đóng góp ý kiến!"

        if score > HIGH_THRESHOLD:
            yield f"data: {json.dumps({'log': f'=> Được trả lời'})}\n\n"
            answer = llm_answer(q, context)
            session_history.append({
                "text": answer,
                "embedding": get_embedding(answer)
            })
            yield f"data: {json.dumps({'replies': answer, 'chunks': chunks})}\n\n"
            return

        elif score < LOW_THRESHOLD:
            session_history.clear()
            yield f"data: {json.dumps({'replies': out_of_score_content, 'chunks': chunks})}\n\n"
            return
        
        elif score <= HIGH_THRESHOLD:
            yield f"data: {json.dumps({'log': f'Sử dụng LLM kiểm tra phạm vi'})}\n\n"
            flow_query = detect_query(q)
            if flow_query in ["qa", "complaint", "out_of_scope"]:
                if flow_query == "qa":
                    yield f"data: {json.dumps({'log': f'=> Được trả lời'})}\n\n"
                    answer = llm_answer(q, context)
                    session_history.append({
                        "text": answer,
                        "embedding": get_embedding(answer)
                    })
                    yield f"data: {json.dumps({'replies': answer, 'chunks': chunks})}\n\n"
                if flow_query == "complaint":
                    yield f"data: {json.dumps({'log': f'=> Phản hồi góp ý'})}\n\n"
                    session_history.clear()
                    yield f"data: {json.dumps({'replies': complaint_content, 'chunks': chunks})}\n\n"
                if flow_query == "out_of_scope":
                    yield f"data: {json.dumps({'log': f'=> Ngoài phạm vi'})}\n\n"
                    session_history.clear()
                    yield f"data: {json.dumps({'replies': out_of_score_content, 'chunks': chunks})}\n\n"
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
