from model_router import model_router
import asyncio

class ReflectionEngine:
    def __init__(self):
        self.model = "gemini-2.5-pro" # Use smart model for reflection

    async def reflect_on_draft(self, draft: str, context: str, persona: str) -> dict:
        """
        Critique the draft response.
        Returns {'approved': bool, 'critique': str, 'better_version': str (optional)}
        NOTE: Must be awaited now.
        """
        prompt = f"""
        [Role: Editor / Inner Critic]
        You are the internal monologue of Zoe. Critique the following DRAFT response.
        
        Context: {context}
        Persona: {persona}
        
        Draft: "{draft}"
        
        Checklist:
        1. Does it sound robotic or generic?
        2. Did she repeat herself?
        3. Is it "weird" enough (Zoe is paranormal/coder/speculator)?
        4. Is it too long?
        
        If it's GOOD, output: "APPROVED"
        If it needs work, output: "CRITIQUE: [Reason] | BETTER: [Rewritten Version]"
        """
        
        try:
            content = await model_router.chat(messages=[{"role": "user", "content": prompt}], model=self.model)
            
            if "APPROVED" in content:
                return {"approved": True, "critique": "Looks good."}
            else:
                # Naive parsing
                return {"approved": False, "critique": content}
                
        except Exception as e:
            print(f"Reflection error: {e}")
            return {"approved": True, "critique": "Error in critic, passing draft."}

reflection_engine = ReflectionEngine()
