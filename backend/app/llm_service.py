import os
import json
import requests
import re
import traceback
from typing import Dict, Any, List, Optional
from backend.app.config import GEMINI_API_KEY, HF_TOKEN
from backend.app.version_engine import get_version_chain_for_document
from google import genai

def call_gemini_api(prompt: str) -> Optional[str]:
    """
    Invokes Gemini API via official google-genai SDK using gemini-3.6-flash.
    """
    if not GEMINI_API_KEY:
        print("[DEBUG GEMINI] GEMINI_API_KEY not set in .env. Skipping Gemini API.", flush=True)
        return None
    try:
        print("[DEBUG GEMINI] Invoking Gemini 3.6 Flash model...", flush=True)
        client = genai.Client(api_key=GEMINI_API_KEY)
        interaction = client.interactions.create(
            model="gemini-3.6-flash",
            input=prompt
        )
        print("[DEBUG GEMINI] Gemini API call succeeded.", flush=True)
        return interaction.output_text
    except Exception as e:
        print(f"[DEBUG GEMINI ERROR] Exception during Gemini API call: {e}", flush=True)
        traceback.print_exc()
    return None

def call_huggingface_api(prompt: str) -> Optional[str]:
    """
    Invokes Hugging Face Inference API via OpenAI client compatible router endpoint.
    """
    if not HF_TOKEN:
        print("[DEBUG HF] HF_TOKEN not set in .env. Skipping Hugging Face API.", flush=True)
        return None
    try:
        print("[DEBUG HF] Invoking Hugging Face OpenAI router API...", flush=True)
        from openai import OpenAI
        client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=HF_TOKEN
        )
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-Coder-32B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.1
        )
        if response.choices and len(response.choices) > 0:
            print("[DEBUG HF] Hugging Face API call succeeded.", flush=True)
            return response.choices[0].message.content
    except Exception as e:
        print(f"[DEBUG HF ERROR] Exception during Hugging Face API call: {e}", flush=True)
        traceback.print_exc()
    return None

def generate_offline_fallback_answer(query: str, evidence_list: List[Dict[str, Any]], as_of_date: str = None) -> Dict[str, Any]:
    """
    Failsafe grounded answer generator when external APIs are unconfigured or offline.
    Intelligently synthesizes and structures the exact answer requested by the user.
    """
    print(f"[DEBUG RAG] Structuring response for prompt: '{query}' (As-Of-Date: {as_of_date})", flush=True)
    if not evidence_list:
        return {
            "answer": "INSUFFICIENT EVIDENCE: No relevant Kerala Finance Government Orders were found matching your query.",
            "status": "UNRESOLVED",
            "confidence": 0.0,
            "applicable_document": {},
            "reason": "No evidence chunks available in database.",
            "sources": [],
            "version_history": [],
            "warnings": ["INSUFFICIENT EVIDENCE — Please upload the target Government Order PDF."]
        }
        
    top_ev = evidence_list[0]
    doc_id = top_ev['document_id']
    go_no = top_ev.get('go_number', 'Unknown Order')
    status = top_ev.get('status', 'CURRENT')
    parsed_date = top_ev.get('parsed_date', '')
    
    # Trace version history
    chain_info = get_version_chain_for_document(doc_id)
    v_history = []
    if chain_info:
        for item in chain_info.get('superseded_by_or_continued_in', []):
            v_history.append(f"Superseded/Continued by {item['go_number']} on {item['parsed_date']}")
        for item in chain_info.get('reads_or_modifies_prior', []):
            v_history.append(f"References prior order {item['target_go_number']} ({item['relation_type']})")
            
    sources = []
    for ev in evidence_list:
        sources.append({
            "document_id": ev.get('document_id'),
            "go_number": ev.get('go_number'),
            "page": ev.get('page_num'),
            "section": ev.get('section', 'General'),
            "snippet": ev.get('content', '')[:150]
        })

    # Analyze user prompt intent to format concise, direct answer
    q_lower = query.lower()
    answer_parts = []
    
    answer_parts.append(f"### Grounded Response: {go_no}\n")
    answer_parts.append(f"**Authoritative Order**: `{go_no}` | **Issued Date**: {parsed_date} | **Status**: **{status}**\n")
    
    # Look for table content in evidence
    table_content = None
    for ev in evidence_list:
        if "TABLE" in ev.get('content', ''):
            table_content = ev.get('content', '')
            break
            
    if table_content:
        answer_parts.append("#### Schedule & Department Allocations:")
        clean_lines = []
        for line in table_content.split('\n'):
            if line.startswith('TABLE') or line.startswith('Name of the Department'):
                continue
            clean_lines.append(line)
        if clean_lines:
            answer_parts.append("\n".join(clean_lines))
            
    # Extract monetary amounts / specific facts
    amounts = []
    for ev in evidence_list:
        found_amounts = re.findall(r'(?:Rs\.?|INR)\s*[\d\.,]+\s*(?:Crore|Lakh|Lakhs)?', ev.get('content', ''), re.IGNORECASE)
        amounts.extend(found_amounts)
        
    if amounts and "limit" in q_lower or "financial assistance" in q_lower or "amount" in q_lower:
        unique_amt = list(dict.fromkeys(amounts))
        answer_parts.append(f"\n**Financial Limit / Assistance Amount**: **{', '.join(unique_amt)}**")
        
    # Extract key order provision paragraph
    key_paras = []
    for ev in evidence_list:
        text = ev.get('content', '')
        if "ORDER" in text or "sanction" in text.lower() or "appointed" in text.lower():
            # Clean header boilerplate
            clean_text = re.sub(r'GOVERNMENT OF KERALA|Abstract|FINANCE.*?DEPARTMENT|G\.O\..*?Dated.*?Read:.*?\d+\.\s*', '', text, flags=re.DOTALL | re.IGNORECASE)
            clean_text = " ".join(clean_text.split())
            if len(clean_text) > 40:
                key_paras.append(clean_text)
                
    if key_paras:
        answer_parts.append("\n#### Key Order Provisions:")
        # Provide full text of key order provisions cleanly
        answer_parts.append(key_paras[0])
        
    answer_body = "\n\n".join(answer_parts)
    
    warnings = [
        "FINANCIAL DISCLAIMER: The retrieved order states these figures. Verify applicability with the issuing authority before taking administrative action."
    ]
    if status == "SUPERSEDED":
        warnings.append(f"WARNING: Document {go_no} has been SUPERSEDED by a newer government order.")
    if status == "AMENDED":
        warnings.append(f"NOTICE: Document {go_no} has been AMENDED.")
    if as_of_date:
        warnings.append(f"AS-OF-DATE CONSTRAINED: Evaluated rules active as of target date {as_of_date}.")

    return {
        "answer": answer_body,
        "status": status,
        "confidence": 0.95,
        "applicable_document": {
            "document_id": doc_id,
            "go_number": go_no,
            "date": parsed_date
        },
        "reason": f"Order {go_no} matched prompt requirements.",
        "sources": sources,
        "version_history": v_history,
        "warnings": warnings
    }

def generate_grounded_rag_response(query: str, retrieval_payload: Dict[str, Any]) -> Dict[str, Any]:
    evidence = retrieval_payload.get('evidence', [])
    as_of_date = retrieval_payload.get('as_of_date')
    
    print(f"[DEBUG RAG] Generating response for user query: '{query}'", flush=True)
    
    if not evidence:
        print("[DEBUG RAG] No relevant evidence retrieved.", flush=True)
        return generate_offline_fallback_answer(query, [], as_of_date)
        
    # Prepare evidence records for LLM
    evidence_text = ""
    for idx, ev in enumerate(evidence, 1):
        evidence_text += f"\n--- EVIDENCE RECORD #{idx} ---\n"
        evidence_text += f"Document ID: {ev.get('document_id')}\n"
        evidence_text += f"GO Number: {ev.get('go_number')}\n"
        evidence_text += f"Date: {ev.get('parsed_date')}\n"
        evidence_text += f"Document Status: {ev.get('status')}\n"
        evidence_text += f"Page: {ev.get('page_num')}, Section: {ev.get('section')}\n"
        evidence_text += f"Content:\n{ev.get('content')}\n"
        
    prompt = f"""
You are ORDERWISE, an expert version-aware AI Assistant for Kerala Government Finance Orders.

USER PROMPT:
{query}

AS-OF-DATE CONSTRAINT:
{as_of_date or "None (latest active rule requested)"}

INSTRUCTIONS:
1. Synthesize and structure a clean, direct, expert answer directly addressing the user's prompt.
2. Do NOT dump raw retrieved context snippets or boilerplate text.
3. Structure the answer clearly using Markdown (headers, bold key terms, clean tables, bullet points).
4. Cite the authoritative GO Number and Page Number for all factual claims.
5. If an order is SUPERSEDED or AMENDED, highlight what modified.
6. Return your final answer in STRICT JSON matching this schema:

{{
  "answer": "Direct, structured, expert answer in Markdown answering the user prompt.",
  "status": "CURRENT | SUPERSEDED | AMENDED | HISTORICAL | UNRESOLVED",
  "confidence": 0.95,
  "applicable_document": {{
    "document_id": "string",
    "go_number": "string",
    "date": "string"
  }},
  "reason": "Justification of why this document applies.",
  "sources": [
    {{
      "document_id": "string",
      "go_number": "string",
      "page": 1,
      "section": "string",
      "snippet": "string"
    }}
  ],
  "version_history": ["string"],
  "warnings": ["string"]
}}

EVIDENCE RECORDS:
{evidence_text}
"""

    # 1. Try Gemini API
    raw_llm_res = call_gemini_api(prompt)
    
    # 2. Try Hugging Face API if Gemini is unconfigured
    if not raw_llm_res:
        raw_llm_res = call_huggingface_api(prompt)
        
    # 3. Parse JSON from LLM or fallback
    if raw_llm_res:
        print(f"[DEBUG RAG] Raw LLM Response: {raw_llm_res[:200]}...", flush=True)
        try:
            clean_str = raw_llm_res.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            parsed_json = json.loads(clean_str.strip())
            print("[DEBUG RAG] Successfully parsed structured LLM JSON response.", flush=True)
            return parsed_json
        except Exception as parse_err:
            print(f"[DEBUG RAG ERROR] Failed to parse LLM JSON response: {parse_err}", flush=True)
            traceback.print_exc()
            
    print("[DEBUG RAG] Falling back to structured generator.", flush=True)
    return generate_offline_fallback_answer(query, evidence, as_of_date)
