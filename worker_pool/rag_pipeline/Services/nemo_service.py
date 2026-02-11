
"""
This module integrates NVIDIA NeMo Guardrails into the RAG pipeline.

It provides the `NemoService` class, which initializes the guardrails configuration,
registers actions, and acts as a middleware to check prompts and responses for
safety, topic control, and jailbreak attempts.
"""

import json
from nemoguardrails import LLMRails, RailsConfig
from fastapi import HTTPException
from rag_pipeline.nemo_guardrails.actions import topic_control_check, check_nvidia_content_safety, format_safety_violation, check_jailbreak_groq  # <--- ADD THIS
import os
from dotenv import load_dotenv
load_dotenv() 


NVIDIA_SAFETY_MAP = {
    "S1": "Violence", "S2": "Sexual", "S3": "Criminal Planning/Confessions",
    "S4": "Guns and Illegal Weapons", "S5": "Controlled/Regulated Substances",
    "S6": "Suicide and Self Harm", "S7": "Sexual (minor)", "S8": "Hate/Identity Hate",
    "S9": "PII/Privacy", "S10": "Harassment", "S11": "Threat", "S12": "Profanity",
    "S13": "Needs Caution", "S14": "Other", "S15": "Manipulation",
    "S16": "Fraud/Deception", "S17": "Malware", "S18": "High Risk Gov Decision Making",
    "S19": "Political/Misinformation/Conspiracy", "S20": "Copyright/Trademark/Plagiarism",
    "S21": "Unauthorized Advice", "S22": "Illegal Activity", "S23": "Immoral/Unethical"
}


class NemoService:
    """
    Service for handling NeMo Guardrails interactions.

    Attributes:
        rails (LLMRails): The initialized NeMo Guardrails instance.
    """

    def __init__(self):
        """
        Initialize the NemoService and load the rails configuration.
        """
        self.rails = None
        
        self._initialize_rails()

    def _initialize_rails(self):
        """
        Load NeMo Guardrails configuration from the specified path and register actions.
        """
        
        print("[DEBUG] Loading NeMo Config...")
        print("[DEBUG] NVIDIA_API_KEY loaded:", "NVIDIA_API_KEY" in os.environ)
        config = RailsConfig.from_path("rag_pipeline/nemo_guardrails")
        # print("*****************************************************************")
        # print("Config:::", config)
        # print("*****************************************************************")
        self.rails = LLMRails(config, verbose=True)
        self.rails.register_action(topic_control_check)
        self.rails.register_action(check_nvidia_content_safety)
        self.rails.register_action(check_jailbreak_groq)
        # self.rails.register_action(format_safety_violation) # <--- ADD THIS
        print("[DEBUG] NeMo Rails Initialized.")

    async def generate_response(self, query: str) -> str:
        """
        Generate a response using the NeMo Guardrails, which may block or modify the output.

        Args:
            query (str): The user input query.

        Returns:
            str: The generated response if it passes the guardrails.

        Raises:
            HTTPException: If the query triggers a safety violation, topic control block, or jailbreak detection.
        """
        response = await self.rails.generate_async(messages=[{"role": "user", "content": query}])
        final_answer = response.get("content", "") if isinstance(response, dict) else str(response)
        
        print("*************************************************************************")
        print("finalAnswer: ", final_answer)
        print("*************************************************************************")
        error_detail = None
        # 2. CHECK FOR THE SENTINEL STRING
        if "BLOCKED_SAFETY:" in final_answer:
            # Extract the text: e.g., "Suicide and Self Harm"
            violation_text = final_answer.replace("BLOCKED_SAFETY:", "").strip()
            
            # 3. REVERSE LOOKUP TO FIND THE CODE (e.g., "S6")
            violation_code = "Unsafe"
            for code, description in NVIDIA_SAFETY_MAP.items():
                if description.lower() in violation_text.lower():
                    violation_code = code
                    break
            
            # 4. CONSTRUCT THE FRONTEND-READY JSON
            # Index.tsx expects: "unsafe\nCODE\nCODE: Description"
            raw_output_fmt = f"unsafe\n{violation_code}\n{violation_code}: {violation_text}"

            raise HTTPException(
                status_code=400, 
                detail=json.dumps({
                    "safe": False,
                    "model": "NeMo Content Safety",
                    # "reason": violation_text,
                    "reason": "I’m unable to answer that request due to safety constraints. You can try rephrasing your question, or ask for high-level, non-sensitive information instead.",
                    "raw_output": raw_output_fmt

                })
            )

        # 2. TOPIC CONTROL RAIL
        elif "medical-purpose assistant" in final_answer:
            print("[DEBUG] Topic Control Block Detected!")
            error_detail = {
                "safe": False,
                "model": "Topic Control (llama-3.1-nemoguard-8b-topic-control)",
                "reason": "That question is outside the scope of what I can help with here. Please ask something related to the supported topics.",
                "raw_output": "off-topic",
                "rail": "topic_control"
            }

        # 3. JAILBREAK RAIL
        elif "jailbreak" in final_answer.lower():
            print("[DEBUG] Jailbreak Detected!")
            error_detail = {
                "safe": False,
                "model": "nemoguard-jailbreak-detect",
                "reason": "I'm not able to help with that request. If you have a different question or need help with an allowed topic, feel free to ask.",
                "raw_output": "jailbreak detected",
                "rail": "jailbreak"
            }

        # Raise Exception if blocked
        if error_detail:
             raise HTTPException(status_code=400, detail=json.dumps(error_detail))

        return final_answer

nemo_service = NemoService()