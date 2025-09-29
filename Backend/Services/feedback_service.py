# Services/feedback_service.py

import os
from opentelemetry import trace
from opentelemetry.trace import SpanContext, TraceFlags, set_span_in_context

# Get a "tracer" object from the global provider configured in main.py
tracer = trace.get_tracer("feedback.service.tracer")

def record_feedback(trace_id: str, feedback: str):
    """
    Creates and sends a new feedback span that is explicitly linked to an
    existing trace_id using the OpenTelemetry SDK.
    """
    try:
        # 1. Convert the incoming hex trace_id string (UUID or OTel format) to an integer
        trace_id_int = int(trace_id.replace("-", ""), 16)
        
        # 2. Create a new random ID for this feedback span
        span_id_int = int.from_bytes(os.urandom(8), "big")

        # 3. Create a SpanContext to link our new span to the existing trace
        # This is the crucial step that connects the feedback to the query
        span_context = SpanContext(
            trace_id=trace_id_int,
            span_id=span_id_int,
            is_remote=False,
            trace_flags=TraceFlags(0x01)  # Mark as sampled
        )
        
        ctx = set_span_in_context(span_context)

        # 4. Start a new span, passing the context to link it to the original trace.
        # The `with` statement ensures the span is properly ended and sent.
        with tracer.start_as_current_span("user.feedback", context=ctx) as span:
            # 5. Set the feedback as attributes on the new span
            if feedback in ["Positive", "Negative"]:
                span.set_attribute("feedback.rating", feedback)
            else:
                span.set_attribute("feedback.comment", feedback)
            
            print(f"Feedback span for trace {trace_id} sent via OTel SDK.")
            
    except Exception as e:
        print(f"Error sending feedback via OTel SDK for trace {trace_id}: {e}")
        raise