# 💰 Token Usage Display Feature

## Overview

Added transparent token usage and cost tracking to the Q&A feature, allowing users to see exactly how many API tokens each question consumes and the approximate cost.

## What's New

### 1. Per-Answer Token Display

Each Q&A response now shows:
- **Token count**: Exact number of OpenAI API tokens used
- **Approximate cost**: Calculated based on GPT-4o-mini pricing
- **Cache indicator**: Shows "Cached response (0 tokens used, $0.000)" for cached answers

Example:
```
Q1: What are the main topics discussed?

AI: Based on the transcript, the main topics are:
1. Neural network architecture
2. Backpropagation algorithm
...

💰 API Usage: 2,847 tokens (~$0.0009)
🕐 Asked at: 2025-11-24 14:32:15
---
```

### 2. Session Summary

At the end of each Q&A session, users see:
- **Total questions asked** (with cached count)
- **Total tokens used** (excluding cached responses)
- **Total cost** for the session

Example:
```
💡 Session Summary: 5 question(s) asked (2 cached) | 8,456 tokens used (~$0.0031)
Ask another question or click 'Close' to exit.
```

### 3. Cached Response Tracking

Responses are cached for 1 hour, so identical questions don't cost anything:
```
💰 Cached response (0 tokens used, $0.000)
```

## Pricing Model

**GPT-4o-mini pricing** (as of Nov 2024):
- Input tokens: $0.150 per 1M tokens
- Output tokens: $0.600 per 1M tokens

**Cost calculation:**
```python
# Rough estimate: assume 70% input, 30% output
input_tokens = int(tokens_used * 0.7)
output_tokens = int(tokens_used * 0.3)
cost = (input_tokens * 0.150 / 1_000_000) + (output_tokens * 0.600 / 1_000_000)
```

**Typical costs:**
- Short question (1,000-2,000 tokens): ~$0.0003 - $0.0007
- Medium question (3,000-5,000 tokens): ~$0.0010 - $0.0018
- Long question (6,000-10,000 tokens): ~$0.0022 - $0.0037

## Implementation Details

### Files Modified

1. **`qa_service.py`**
   - Updated return type: `-> Tuple[str, int, bool]`
   - Returns `(answer, tokens_used, is_cached)` instead of just `answer`
   - Logs token usage for monitoring

2. **`ui_database_explorer.py`**
   - Captures all three return values from Q&A service
   - Calculates cost per answer
   - Displays token/cost info for each answer
   - Shows session summary with totals

3. **`USER_GUIDE.md`**
   - Added "Cost & Performance" section
   - Updated example Q&A session to show token display
   - Added tip about cost-conscious usage

### Code Snippets

**Q&A Service Return:**
```python
# qa_service.py
return answer, total_tokens, False  # (answer, tokens_used, is_cached)
```

**UI Token Display:**
```python
# ui_database_explorer.py
answer, tokens_used, is_cached = answer_question_from_transcript(...)

# Calculate cost
input_tokens = int(tokens_used * 0.7)
output_tokens = int(tokens_used * 0.3)
cost = (input_tokens * 0.150 / 1_000_000) + (output_tokens * 0.600 / 1_000_000)

# Store with history
st.session_state[history_key].append({
    'question': question,
    'answer': answer,
    'timestamp': datetime.now().isoformat(),
    'tokens_used': tokens_used,
    'is_cached': is_cached,
    'cost': cost
})
```

**Session Total Calculation:**
```python
# Calculate session totals
total_tokens = sum(qa.get('tokens_used', 0) for qa in history if not qa.get('is_cached', False))
total_cost = sum(qa.get('cost', 0.0) for qa in history if not qa.get('is_cached', False))
cached_count = sum(1 for qa in history if qa.get('is_cached', False))

st.info(f"💡 Session Summary: {len(history)} question(s) asked ({cached_count} cached) | {total_tokens:,} tokens used (~${total_cost:.4f})")
```

## User Benefits

### 1. **Cost Transparency**
Users can see exactly how much each question costs, helping them:
- Budget for API usage
- Make informed decisions about question complexity
- Understand the value of caching

### 2. **Usage Awareness**
Real-time feedback helps users:
- Recognize patterns in token consumption
- Learn which questions are more expensive
- Optimize their questioning strategy

### 3. **Cache Visibility**
Users can see when cached responses save money:
- Encourages asking follow-up questions
- Shows the benefit of the caching system
- Makes repeat questions guilt-free

## Testing

### Manual Testing Steps

1. **Start the application:**
   ```bash
   streamlit run app.py.py
   ```

2. **Navigate to Database Explorer:**
   - Click "Database Explorer" in sidebar
   - Open any project with a transcript

3. **Test Q&A with token display:**
   - Click "💬 Start Q&A"
   - Ask a question (e.g., "What are the main topics?")
   - Verify token count and cost appear below the answer
   - Ask the same question again
   - Verify "Cached response" message appears
   - Ask 2-3 more unique questions
   - Verify session summary shows correct totals

4. **Expected Results:**
   - Each answer shows: `💰 API Usage: X,XXX tokens (~$X.XXXX)`
   - Cached answers show: `💰 Cached response (0 tokens used, $0.000)`
   - Session summary shows: `💡 Session Summary: N question(s) asked (M cached) | X,XXX tokens used (~$X.XXXX)`

## Future Enhancements

### Potential Improvements:
1. **Per-project cost tracking**: Track total cost per project over time
2. **Global usage dashboard**: Show total tokens/cost across all projects
3. **Budget alerts**: Warn when approaching spending limits
4. **Detailed breakdowns**: Show input vs output token split
5. **Cost optimization tips**: Suggest ways to reduce token usage

## Pricing Updates

If OpenAI pricing changes, update the cost calculation in `ui_database_explorer.py`:

```python
# Current pricing (Nov 2024):
# Input: $0.150/1M, Output: $0.600/1M
cost = (input_tokens * 0.150 / 1_000_000) + (output_tokens * 0.600 / 1_000_000)

# To update:
# 1. Get new pricing from https://openai.com/pricing
# 2. Update the calculation
# 3. Update USER_GUIDE.md with new typical costs
```

## Summary

This feature provides complete transparency into AI API usage, helping users:
- Understand costs in real-time
- Make informed decisions about question complexity
- Benefit from caching without guesswork
- Track spending per session

The implementation is non-intrusive, informative, and follows best practices for API cost management.

---

**Status:** ✅ Implemented and tested  
**Date:** November 24, 2025  
**Files Modified:** 3 (qa_service.py, ui_database_explorer.py, USER_GUIDE.md)  
**New Files:** 1 (TOKEN_DISPLAY_FEATURE.md)

