from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import re
import ollama

# -----------------------------------
# APP INIT
# -----------------------------------
app = FastAPI()

# -----------------------------------
# API Request Model
# -----------------------------------
class EmailRequest(BaseModel):
    email: str

# -----------------------------------
# RULE ENGINE
# -----------------------------------
RULES = {
    "TRACK_ORDER": ["where is my order", "track my order", "order status"],
    "ORDER_NOT_RECEIVED": ["not received", "did not receive", "missing"],
    "DELIVERY_FAILED": ["not present", "missed delivery", "not available"],
    "CANCEL_ORDER": ["cancel my order", "cancel order"],
    "CHANGE_ADDRESS": ["change address", "update address"],
    "DELAY_QUERY": ["delayed", "why late", "delay in order"],
    "ESCALATION_REQUEST": ["speak to manager", "escalate"],
    "COMPLAINT": ["complaint", "bad service"]
}

# -----------------------------------
# PROCESSOR CLASS
# -----------------------------------
class EmailProcessor:

    def process(self, text: str):
        text = text.lower() 

        #intent = self.rule_based(text)
        #intents = self.detect_multiple_intents(text)
        #intent = intents[0] if intents else "UNKNOWN"
        intent = "UNKNOWN"
        # LLM fallback
        if intent == "UNKNOWN":
            intent = self.llm(text)
            intents = [intent]

        entities = self.extract(text)
        context = self.extract_context(text)
        sentiment = self.extract_sentiment(text)
        response = self.respond(intent, intents, entities, context, sentiment)

        return {  
            "primary_intent": intent,
            "all_intents": intents,
            "entities": entities,
            "context": context,
            "sentiment": sentiment,
            "response": response
        }

    # -----------------------------------
    def rule_based(self, text):
        for intent, keywords in RULES.items():
            if any(k in text for k in keywords):
                return intent
        return "UNKNOWN"

    # MULTI-INTENT DETECTION
    def detect_multiple_intents(self, text):
        intents = []

        for intent, keywords in RULES.items():
            if any(k in text for k in keywords):
                intents.append(intent)

        return intents if intents else ["UNKNOWN"]
   
    # -----------------------------------
    def llm(self, text):
        try:
            res = ollama.chat(
                model="mistral",
                messages=[{"role": "user", "content": text}]
            )
            print("OLLAMA RAW RESPONSE:", res)
           
            content = res.get("message", {}).get("content", "").strip()
            if not content:
                print("Empty LLM response")
                return "UNKNOWN LLM"

            return content
       
        except Exception as e:
                print("OLLAMA ERROR:", e)
                return "UNKNOWN"


    # -----------------------------------
    def extract(self, text):
        match = re.search(r"\d{5,}", text)
        return {"order_id": match.group() if match else None}
   
    # -----------------------------------
    def extract_context(self, text):
        context = []

        if "earlier" in text or "again" in text or "already" in text:
            context.append("repeat_issue")

        if "not received" in text:
            context.append("delivery_pending")

        if "missed delivery" in text or "not present" in text:
            context.append("delivery_failed")

        if "urgent" in text or "asap" in text:
            context.append("high_priority")
       
        if "refund" in text:
            context.append("refund_expected")

        if "manager" in text or "complaint" in text:
                context.append("needs_escalation")

        return context

    # ------------------------
    def extract_sentiment(self, text):
        negative_words = ["not happy", "very bad", "worst", "frustrated",
            "not satisfied", "disappointed", "issue", "problem",
            "this is not acceptable", "unhappy"
        ]
        positive_words = ["thank you", "thanks", "great", "good",
            "happy", "appreciate", "excellent"
        ]

        for w in negative_words:
            if w in text:
                return "negative"

        for w in positive_words:
            if w in text:
                return "positive"

        if "not" in text:
                return "negative"

        return "neutral"

    # -----------------------------------
    def respond(self, intent, intents, entities, context, sentiment):
        oid = entities.get("order_id", "your order")
       
        # context priority
        if "high_priority" in context:
            return f"⚡ We are prioritizing your request for order {oid}."

        if "needs_escalation" in context:
            return f"🚨 Your issue has been escalated to our support team."

        if intent == "COMPLAINT":
            return "⚠️ We regret the inconvenience. Your complaint has been logged"

        # multi-intent logic (NEW)
        if len(intents) > 1:
            return f"🔍 We identified multiple requests ({', '.join(intents)}). Our team will handle them together."

        # intent logic
        if intent == "TRACK_ORDER":
            return f"✅ Order {oid} is on the way."

        elif intent == "ORDER_NOT_RECEIVED":
           
            if "repeat_issue" in context:
                return f"⚠️ Repeated issue. Order {oid} escalated."

            return f"⏳ Order {oid} will arrive in 24–48 hours."


        elif intent == "DELIVERY_FAILED":
            return f"🚚 Delivery missed for order {oid}. Reschedule or cancel?"
       
        elif intent == "CANCEL_ORDER":
                return f"❌ Order {oid} cancellation request received."

        return "⚠️ We couldn’t understand your request. Our team will assist shortly."


# -----------------------------------
# INIT PROCESSOR
# -----------------------------------
processor = EmailProcessor()

# -----------------------------------
# GUI (NO JINJA)
# -----------------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <body>
        <h2>Email Processing Tool</h2>

        <form method="post">
            <textarea name="email" rows="4" cols="50"
            placeholder="Enter email..."></textarea><br><br>
            <button type="submit">Process</button>
        </form>
    </body>
    </html>
    """


@app.post("/", response_class=HTMLResponse)
def process(email: str = Form(...)):
    result = processor.process(email)

    intent = result.get("all_intents")
    order_id = result.get("entities", {}).get("order_id")
    context = result.get("context")
    sentiment = result.get("sentiment")
    response = result.get("response")

    return f"""
    <html>
    <body>

        <h2>Email Processing Tool</h2>

        <form method="post">
            <textarea name="email" rows="4" cols="50">{email}</textarea><br><br>
            <button type="submit">Process</button>
        </form>

        <hr>
        <h3>Result:</h3>
        <p><b>Intents:</b> {intent}</p>
        <p><b>Order ID:</b> {order_id}</p>
        <p><b>Context:</b> {context}</p>
        <p><b>Sentiment:</b> {sentiment}</p>
        <p><b>Response:</b> {response}</p>

    </body>
    </html>
    """


# -----------------------------------
# API (Power Automate)
# -----------------------------------
@app.post("/process-email")
def process_email(req: EmailRequest):
    result = processor.process(req.email)

    return {
        "intents": result["all_intents"],
        "entities": result["entities"],
        "context": result["context"],
        "sentiment": result["sentiment"],
        "response": result["response"],
        "timestamp": str(datetime.now())
    }

