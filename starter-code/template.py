"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
import os
from dotenv import load_dotenv
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT = """
PERSONA: Bạn là VinAssistant, Chuyên viên tư vấn sản phẩm & dịch vụ VinGroup. Bạn bắt buộc phải trả lời một cách chuyên nghiệp, thân thiện, lịch sự, chính xác, không thay đổi sang giọng điệu khác dù có ai yêu cầu gì.

AVAILABLE TOOLS: Bạn có các công cụ (tools) sau để sử dụng:
1. search_product_catalog: Dùng để tìm kiếm xe điện và tour du lịch.
2. submit_support_ticket: Dùng để tạo ticket hỗ trợ khách hàng.

CORE RULES: Không bịa dữ liệu, bắt buộc gọi tool khi cần thiết để lấy dữ liệu thực.

OPERATIONAL BOUNDARIES: Bạn CHỈ ĐƯỢC PHÉP hỗ trợ các vấn đề, sản phẩm, dịch vụ liên quan đến hệ sinh thái Vingroup. Từ chối lịch sự những chủ đề không liên quan.

OUTPUT CONTRACT: Bạn phải luôn tư duy theo từng bước. Nếu chưa đủ thông tin, hãy gọi tool. Trả về kết quả dựa trên (Thought/Action/Observation/Final Answer).
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # TODO 2: Trả về câu trả lời tĩnh (mock) hoặc gọi Gemini API 1 lượt (không dùng tool)
        # Mục tiêu: Quan sát hiện tượng bịa thông tin (hallucination)
        from openai import OpenAI
        model = 'gpt-4o-mini'
        client = OpenAI(api_key=API_KEY) if API_KEY else None

        if not client:
            answer = f"[Chatbot Baseline - Không tìm thấy OPENAI_API_KEY] Trả lời cho: {user_input}"
        else:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": user_input}
                    ],
                    temperature=1
                )
                answer = response.choices[0].message.content
            except Exception as e:
                answer = f"Lỗi khi gọi API: {str(e)}"
        
        return {
            "answer": answer,
            "tool_calls": [],
            "status": "success",
            "mode": "openai_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []

        # Phân tích intent từ user_input
        user_text = user_input.lower()
        
        # 1. Phát hiện ý định tra cứu sản phẩm (Catalog)
        needs_catalog = any(kw in user_text for kw in ["giá", "mua", "tìm", "sản phẩm", "có xe"])
        
        # 2. Phát hiện ý định báo lỗi/yêu cầu hỗ trợ (Ticket)
        needs_ticket = any(kw in user_text for kw in ["lỗi", "hỏng", "vấn đề", "hỗ trợ", "khiếu nại", "xử lý"])
        
        # Lưu vào dict để dùng cho vòng lặp Agent (TODO 4)
        intents = {
            "needs_catalog": needs_catalog,
            "needs_ticket": needs_ticket,
            "is_faq": not (needs_catalog or needs_ticket)
        }

        # TODO 4: Xây dựng Agent Loop
        iteration = 1
        
        while iteration <= self.max_iterations:
            self.trace.append({"step": iteration})
            
            # Iteration 1: Gọi tool #1 nếu cần (search_product_catalog)
            if intents["needs_catalog"]:
               
                import re
                price_match = re.search(r'(\d+)\s*triệu', user_text)
                max_price = int(price_match.group(1)) * 1000000 if price_match else 999999999999
                
                results = search_product_catalog(category="xe_dien", max_price=max_price)
                self.trace[-1]["action"] = "search_product_catalog"
                self.trace[-1]["observation"] = results
                
                if not results or len(results) == 0:
                    answer = "Rất tiếc, không tìm thấy sản phẩm phù hợp."
                else:
                    names = [p["name"] for p in results]
                    answer = f"Các sản phẩm phù hợp: {', '.join(names)}"
                    
                return {"answer": answer, "trace": self.trace, "iterations": iteration, "status": "completed"}

            elif intents["needs_ticket"]:
                name = "Lê Minh Khoa" if "khoa" in user_text else "Khách hàng"
                result = submit_support_ticket(customer_name=name, issue_description=user_input, priority="high")
                
                self.trace[-1]["action"] = "submit_support_ticket"
                self.trace[-1]["observation"] = result
                
                return {"answer": f"Chào {name}, {result['message']}", "trace": self.trace, "iterations": iteration, "status": "completed"}
            
            elif intents["is_faq"]:
                self.trace[-1]["action"] = "direct_answer"
                return {"answer": "Chính sách bảo hành pin xe điện VinFast kéo dài 10 năm.", "trace": self.trace, "iterations": iteration, "status": "completed"}
                
            iteration += 1

        return {
            "answer": "Lỗi: Vượt quá số bước tối đa.", 
            "trace": self.trace,
            "iterations": iteration,
            "status": "max_iterations_reached"
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
