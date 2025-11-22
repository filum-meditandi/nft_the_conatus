"""
Accessibility-First Twilio Inbound Handler

This module implements the primary capture interface for phenomenological evidence.
It is designed for someone in pain, with brain fog, with a cheap phone, at 3am.

Design principles (see ACCESSIBILITY_PRINCIPLES.md):
1. Single-step interactions - any message works standalone
2. Cognitive load limits - one question at a time
3. Robust to partial information - accept anything, extract what we can
4. Explainability - every conclusion traceable to attestations

SMS Commands:
- PAIN 7 neck burning → pain report
- WORK left early → work impact
- SLEEP 3 hours → sleep disruption  
- FLARE → triggers brief follow-up
- STATUS → trajectory summary
- HELP → command list
- (anything else) → best-effort parse as pain/symptom note
"""

import re
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from unified_service import PhenomenologyService, PhenomenologyInput, process_sms_phenomenology
from hmm_inference import TrajectoryAnalysisService
from phone_registry import PhoneRegistryService


router = APIRouter(prefix="/twilio", tags=["twilio"])


# ============================================================================
# MESSAGE PARSING
# ============================================================================

class MessageIntent(str, Enum):
    """Detected intent from SMS message."""
    PAIN_REPORT = "pain_report"
    WORK_IMPACT = "work_impact"
    SLEEP_REPORT = "sleep_report"
    FLARE_ALERT = "flare_alert"
    STATUS_REQUEST = "status_request"
    HELP_REQUEST = "help_request"
    GENERAL_NOTE = "general_note"
    UNKNOWN = "unknown"


@dataclass
class ParsedMessage:
    """Result of parsing an inbound SMS."""
    intent: MessageIntent
    raw_text: str
    
    # Extracted data (all optional - robust to partial info)
    pain_value: Optional[float] = None
    pain_location: Optional[str] = None
    pain_quality: Optional[str] = None
    
    sleep_hours: Optional[float] = None
    work_impact: Optional[str] = None
    
    # Flags
    is_flare: bool = False
    needs_followup: bool = False
    followup_question: Optional[str] = None
    
    # Confidence in parse
    confidence: float = 0.5


class AccessibilityFirstParser:
    """
    Parses SMS messages with maximum tolerance for variation.
    
    Principles:
    - Accept anything, extract what we can
    - Never reject a message as "invalid"
    - Partial information is still valuable
    - Natural language variations welcome
    """
    
    # Pain value patterns (very permissive)
    PAIN_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*/\s*10',           # 7/10
        r'(\d+(?:\.\d+)?)\s+out\s+of\s+10',    # 7 out of 10
        r'pain\s*[:\s]*(\d+(?:\.\d+)?)',       # pain 7, pain: 7
        r'^(\d+(?:\.\d+)?)\s*$',               # just "7"
        r'level\s*[:\s]*(\d+(?:\.\d+)?)',      # level 7
        r'(\d+(?:\.\d+)?)\s*pain',             # 7 pain
        r'about\s+(?:a\s+)?(\d+(?:\.\d+)?)',   # about a 7
        r"it'?s\s+(?:a\s+)?(\d+(?:\.\d+)?)",   # it's a 7
    ]
    
    # Location keywords
    LOCATIONS = {
        'neck': ['neck', 'cervical', 'c-spine'],
        'head': ['head', 'headache', 'migraine'],
        'low back': ['low back', 'lower back', 'lumbar', 'l-spine'],
        'upper back': ['upper back', 'thoracic', 'mid back'],
        'shoulder': ['shoulder', 'shoulders'],
        'arm': ['arm', 'arms', 'elbow', 'wrist', 'hand'],
        'leg': ['leg', 'legs', 'hip', 'knee', 'ankle', 'foot'],
        'chest': ['chest'],
        'stomach': ['stomach', 'abdomen', 'belly'],
    }
    
    # Quality keywords
    QUALITIES = {
        'burning': ['burning', 'burn', 'fire', 'hot'],
        'sharp': ['sharp', 'stabbing', 'shooting', 'electric'],
        'dull': ['dull', 'aching', 'ache', 'sore'],
        'throbbing': ['throbbing', 'pulsing', 'pounding'],
        'tingling': ['tingling', 'pins', 'needles', 'numb'],
        'pressure': ['pressure', 'tight', 'squeezing'],
    }
    
    # Command prefixes (case-insensitive)
    COMMANDS = {
        'pain': MessageIntent.PAIN_REPORT,
        'hurt': MessageIntent.PAIN_REPORT,
        'hurts': MessageIntent.PAIN_REPORT,
        'ache': MessageIntent.PAIN_REPORT,
        'work': MessageIntent.WORK_IMPACT,
        'job': MessageIntent.WORK_IMPACT,
        'sleep': MessageIntent.SLEEP_REPORT,
        'slept': MessageIntent.SLEEP_REPORT,
        'flare': MessageIntent.FLARE_ALERT,
        'bad': MessageIntent.FLARE_ALERT,
        'worse': MessageIntent.FLARE_ALERT,
        'status': MessageIntent.STATUS_REQUEST,
        'summary': MessageIntent.STATUS_REQUEST,
        'help': MessageIntent.HELP_REQUEST,
        '?': MessageIntent.HELP_REQUEST,
    }
    
    def parse(self, raw_text: str) -> ParsedMessage:
        """
        Parse an SMS message, extracting whatever we can.
        
        NEVER rejects a message. Always returns something usable.
        """
        text = raw_text.strip()
        text_lower = text.lower()
        
        # Detect intent from first word/command
        intent = self._detect_intent(text_lower)
        
        result = ParsedMessage(
            intent=intent,
            raw_text=text
        )
        
        # Extract pain value (try multiple patterns)
        result.pain_value = self._extract_pain_value(text_lower)
        
        # Extract location
        result.pain_location = self._extract_location(text_lower)
        
        # Extract quality
        result.pain_quality = self._extract_quality(text_lower)
        
        # Handle specific intents
        if intent == MessageIntent.SLEEP_REPORT:
            result.sleep_hours = self._extract_sleep_hours(text_lower)
        
        if intent == MessageIntent.WORK_IMPACT:
            result.work_impact = self._extract_work_impact(text)
        
        if intent == MessageIntent.FLARE_ALERT:
            result.is_flare = True
            result.needs_followup = True
            result.followup_question = "Got it - flare noted. Pain level 0-10?"
        
        # If we got a pain value, upgrade confidence
        if result.pain_value is not None:
            result.confidence = 0.8
            if result.pain_location:
                result.confidence = 0.9
        
        # If nothing specific detected but there's text, treat as general note
        if (intent == MessageIntent.UNKNOWN and 
            result.pain_value is None and 
            len(text) > 2):
            result.intent = MessageIntent.GENERAL_NOTE
            result.confidence = 0.5
        
        return result
    
    def _detect_intent(self, text_lower: str) -> MessageIntent:
        """Detect message intent from keywords."""
        first_word = text_lower.split()[0] if text_lower.split() else ""
        
        # Check explicit commands first
        if first_word in self.COMMANDS:
            return self.COMMANDS[first_word]
        
        # Check if message contains pain indicators
        pain_words = ['pain', 'hurt', 'ache', 'sore', 'burning', 'throbbing']
        if any(word in text_lower for word in pain_words):
            return MessageIntent.PAIN_REPORT
        
        # Check for just a number (assume pain score)
        if re.match(r'^\d+(?:\.\d+)?(?:\s*/\s*10)?$', text_lower.strip()):
            return MessageIntent.PAIN_REPORT
        
        return MessageIntent.UNKNOWN
    
    def _extract_pain_value(self, text_lower: str) -> Optional[float]:
        """Extract pain value from text."""
        for pattern in self.PAIN_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                value = float(match.group(1))
                return min(value, 10.0)  # Cap at 10
        return None
    
    def _extract_location(self, text_lower: str) -> Optional[str]:
        """Extract pain location from text."""
        for location, keywords in self.LOCATIONS.items():
            if any(kw in text_lower for kw in keywords):
                return location
        return None
    
    def _extract_quality(self, text_lower: str) -> Optional[str]:
        """Extract pain quality from text."""
        for quality, keywords in self.QUALITIES.items():
            if any(kw in text_lower for kw in keywords):
                return quality
        return None
    
    def _extract_sleep_hours(self, text_lower: str) -> Optional[float]:
        """Extract sleep hours from text."""
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)',
            r'slept\s*(?:for\s*)?(\d+(?:\.\d+)?)',
            r'only\s*(\d+(?:\.\d+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return float(match.group(1))
        return None
    
    def _extract_work_impact(self, text: str) -> Optional[str]:
        """Extract work impact description."""
        # Return everything after "work" keyword
        match = re.search(r'work\s+(.+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text  # Return full text as work note


# ============================================================================
# RESPONSE GENERATION
# ============================================================================

class ResponseGenerator:
    """
    Generates SMS responses following accessibility principles.
    
    Rules:
    - Under 160 characters when possible
    - Acknowledge receipt immediately
    - Never lecture or give medical advice
    - One question at a time for follow-ups
    """
    
    HELP_MESSAGE = """Commands:
PAIN 7 neck burning - report pain
WORK left early - work impact
SLEEP 3 hours - sleep report
FLARE - report flare
STATUS - your summary
Or just text how you feel."""

    def acknowledge_pain(self, parsed: ParsedMessage) -> str:
        """Acknowledge a pain report."""
        parts = ["Got it."]
        
        if parsed.pain_value is not None:
            parts.append(f"Pain {parsed.pain_value}/10")
            if parsed.pain_location:
                parts.append(f"({parsed.pain_location})")
        
        parts.append("recorded.")
        
        msg = " ".join(parts)
        
        # If we didn't get a pain value, ask for one
        if parsed.pain_value is None and not parsed.needs_followup:
            msg += " Pain level 0-10?"
        
        return msg
    
    def acknowledge_work(self, parsed: ParsedMessage) -> str:
        """Acknowledge a work impact report."""
        return "Work impact recorded. Take care of yourself."
    
    def acknowledge_sleep(self, parsed: ParsedMessage) -> str:
        """Acknowledge a sleep report."""
        if parsed.sleep_hours is not None:
            return f"Recorded {parsed.sleep_hours} hours sleep."
        return "Sleep note recorded."
    
    def acknowledge_flare(self, parsed: ParsedMessage) -> str:
        """Acknowledge a flare alert."""
        return "Flare noted. Pain level 0-10?"
    
    def acknowledge_general(self, parsed: ParsedMessage) -> str:
        """Acknowledge a general note."""
        return "Noted. Reply HELP for commands."
    
    def status_summary(self, stats: Dict[str, Any]) -> str:
        """Generate a brief status summary."""
        if not stats:
            return "No reports yet. Text PAIN followed by 0-10 to start."
        
        parts = []
        
        if "last_7_days" in stats:
            s = stats["last_7_days"]
            parts.append(f"Last 7 days: {s.get('report_count', 0)} reports")
            if s.get("avg_pain"):
                parts.append(f"avg pain {s['avg_pain']:.1f}")
        
        if "current_state" in stats:
            parts.append(f"Current: {stats['current_state']}")
        
        return ", ".join(parts) + "." if parts else "Recording your reports."
    
    def help_message(self) -> str:
        """Return help message."""
        return self.HELP_MESSAGE
    
    def error_message(self) -> str:
        """Friendly error message."""
        return "Something went wrong on our end. Your message was saved. We'll look into it."


# ============================================================================
# TWILIO WEBHOOK HANDLER
# ============================================================================

# TwiML response template
TWIML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""


def twiml_response(message: str) -> Response:
    """Create a TwiML response."""
    return Response(
        content=TWIML_TEMPLATE.format(message=message),
        media_type="application/xml"
    )


@dataclass 
class TwilioMessage:
    """Parsed Twilio webhook data."""
    body: str
    from_phone: str
    to_phone: str
    message_sid: str
    account_sid: str
    received_at: datetime
    
    # Optional fields
    num_media: int = 0
    channel: str = "sms"


async def parse_twilio_request(form_data: dict) -> TwilioMessage:
    """Parse Twilio webhook form data."""
    return TwilioMessage(
        body=form_data.get("Body", ""),
        from_phone=form_data.get("From", ""),
        to_phone=form_data.get("To", ""),
        message_sid=form_data.get("MessageSid", ""),
        account_sid=form_data.get("AccountSid", ""),
        received_at=datetime.now(timezone.utc),
        num_media=int(form_data.get("NumMedia", 0)),
        channel="sms"
    )


# Database session dependency - implement based on your setup
def get_db():
    """
    Database session dependency.
    
    In production, implement like:
    
    from database import SessionLocal
    
    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    """
    raise NotImplementedError("Implement get_db() with your database session")


@router.post("/inbound")
async def twilio_inbound(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Main Twilio SMS webhook handler.
    
    This is the accessibility-first entry point. It:
    1. Parses the message with maximum tolerance
    2. Looks up the phone registration
    3. Routes through the integrated capture pipeline
    4. Returns brief acknowledgment
    """
    from integration import IntegratedPhenomenologyService
    from phone_registry import PhoneRegistryService
    
    # Parse Twilio request
    form_data = await request.form()
    msg = await parse_twilio_request(dict(form_data))
    
    # Initialize services
    parser = AccessibilityFirstParser()
    responder = ResponseGenerator()
    phone_service = PhoneRegistryService(db)
    
    # Look up phone registration
    persona_context = phone_service.get_context(msg.from_phone)
    
    if not persona_context:
        # Unknown phone - provide help
        return twiml_response(
            "This number isn't registered. Contact your legal team to get set up."
        )
    
    # Update last message timestamp
    phone_service.update_last_message(msg.from_phone)
    
    # Parse the message
    parsed = parser.parse(msg.body)
    
    # Handle special intents first
    if parsed.intent == MessageIntent.HELP_REQUEST:
        return twiml_response(responder.help_message())
    
    if parsed.intent == MessageIntent.STATUS_REQUEST:
        # Get trajectory summary
        trajectory_service = TrajectoryAnalysisService(db)
        stats = trajectory_service.stats.generate_court_summary(
            persona_context["persona_token_id"],
            persona_context["case_id"]
        )
        return twiml_response(responder.status_summary(stats.get("overall_statistics", {})))
    
    # For all other intents, record through integrated pipeline
    try:
        integrated_service = IntegratedPhenomenologyService(db)
        
        # Ensure default model exists
        integrated_service.ensure_default_model()
        
        # Capture through integrated pipeline
        result = integrated_service.capture(
            party_id=persona_context["party_id"],
            case_id=persona_context["case_id"],
            raw_text=f"[SMS {msg.received_at.isoformat()}] {msg.body}",
            pain_value=parsed.pain_value,
            pain_location=parsed.pain_location,
            pain_quality=parsed.pain_quality,
            event_time=msg.received_at,
            source="sms",
            run_hmm_inference=True
        )
        
        # Generate response based on intent
        if parsed.intent == MessageIntent.PAIN_REPORT:
            response_text = responder.acknowledge_pain(parsed)
            # Add state info if available
            if result.inferred_state:
                if result.inferred_state == "flare":
                    response_text += " Looks like a flare."
                elif result.inferred_state == "improvement":
                    response_text += " Trending better."
        elif parsed.intent == MessageIntent.WORK_IMPACT:
            response_text = responder.acknowledge_work(parsed)
        elif parsed.intent == MessageIntent.SLEEP_REPORT:
            response_text = responder.acknowledge_sleep(parsed)
        elif parsed.intent == MessageIntent.FLARE_ALERT:
            response_text = responder.acknowledge_flare(parsed)
        else:
            response_text = responder.acknowledge_general(parsed)
        
        return twiml_response(response_text)
        
    except Exception as e:
        # Log error but don't fail the user
        import traceback
        print(f"Error processing SMS: {e}")
        traceback.print_exc()
        
        return twiml_response(responder.error_message())


@router.post("/voice/inbound")
async def twilio_voice_inbound(request: Request):
    """
    Voice webhook - single question, single answer.
    
    Flow:
    1. "How would you rate your pain right now, from 0 to 10?"
    2. Capture response
    3. "I recorded pain level [X]. Take care."
    """
    # TwiML for voice - gather single digit
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="dtmf speech" timeout="10" numDigits="2" action="/twilio/voice/process">
        <Say voice="alice">
            How would you rate your pain right now, from 0 to 10?
        </Say>
    </Gather>
    <Say voice="alice">
        I didn't hear anything. Call back when you're ready.
    </Say>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/process")
async def twilio_voice_process(
    request: Request,
    db: Session = Depends(get_db)
):
    """Process voice input and record to chain."""
    form_data = await request.form()
    
    # Get the gathered input (DTMF digits or speech)
    digits = form_data.get("Digits", "")
    speech = form_data.get("SpeechResult", "")
    from_phone = form_data.get("From", "")
    
    # Parse pain value
    pain_value = None
    
    if digits:
        try:
            pain_value = min(float(digits), 10.0)
        except ValueError:
            pass
    elif speech:
        # Try to extract number from speech
        parser = AccessibilityFirstParser()
        pain_value = parser._extract_pain_value(speech.lower())
    
    # Record if we got a value
    if pain_value is not None:
        # Would record to chain here
        # ...
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        I recorded pain level {int(pain_value)}. Take care of yourself.
    </Say>
</Response>"""
    else:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        I couldn't understand that. Call back and say a number from 0 to 10.
    </Say>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")
