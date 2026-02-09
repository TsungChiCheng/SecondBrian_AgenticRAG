"""
Session management and enhanced Ask endpoint with Agentic RAG
This file contains the new endpoints to be added to main.py
"""

# Add these endpoints to main.py after the existing routes

# ============ SESSION MANAGEMENT ENDPOINTS ============

@app.post("/sessions/create")
async def create_new_session(
    title: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """Create a new conversation session"""
    try:
        session_id = await create_session(user.id, title)
        return {
            "session_id": session_id,
            "message": "Session created successfully",
            "title": title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions")
async def list_sessions(
    limit: int = 50,
    include_inactive: bool = False,
    user: User = Depends(get_current_user)
):
    """List all sessions for the current user"""
    try:
        sessions = await list_user_sessions(user.id, limit, include_inactive)
        return {
            "sessions": sessions,
            "total": len(sessions)
        }
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """Get session details and message history"""
    try:
        # Get session metadata
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Verify ownership
        if session["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get messages
        messages = await get_session_messages(session_id)
        
        return {
            "session": session,
            "messages": messages,
            "message_count": len(messages)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """Delete a conversation session"""
    try:
        # Verify ownership first
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete the session
        deleted = await delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete session")
        
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/sessions/{session_id}/title")
async def update_session_title_endpoint(
    session_id: str,
    title: str,
    user: User = Depends(get_current_user)
):
    """Update session title"""
    try:
        # Verify ownership
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update title
        updated = await update_session_title(session_id, title)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update the title")
        
        return {"message": "Title updated successfully", "title": title}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session title: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ ENHANCED ASK ENDPOINT ============
# This replaces the existing /ask endpoint

@app.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    user: User = Depends(get_current_user)
):
    """Enhanced ask endpoint with session management and agentic RAG"""
    
    logger.debug(f"📝 Processing question from user {user.name} ({user.email}, ID: {user.id[:8]}...): {request.user_input[:50]}...")
    
    # Session management: Create or use existing session
    session_id = request.session_id
    if not session_id:
        # Create a new session automatically
        session_id = await create_session(user.id, f"Chat {datetime.now().strftime('%H:%M')}")
        logger.info(f"Created new session {session_id} for user {user.id[:8]}...")
    else:
        # Verify session exists and user owns it
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        logger.info(f"Using existing session {session_id}")
    
    # Add user message to session
    await add_message(session_id, "user", request.user_input)
    
    # Decide whether to use Agentic RAG or traditional flow
    if request.use_agentic_rag and os.getenv("OPENAI_API_KEY"):
        logger.info("🤖 Using Agentic RAG workflow")
        
        try:
            # Create the LangGraph workflow
            graph = create_agentic_rag_graph()
            
            # Get recent conversation history
            recent_messages = await get_session_messages(session_id, limit=20)
            
            # Build initial state
            initial_state: ConversationState = {
                "session_id": session_id,
                "user_id": user.id,
                "messages": [{"role": msg["role"], "content": msg["content"]} for msg in recent_messages],
                "current_query": request.user_input,
                "retrieved_context": [],
                "agent_thoughts": [],
                "iteration_count": 0,
                "max_iterations": 3,
                "should_retrieve": True,
                "should_refine": False,
                "final_answer": None,
                "selected_models": request.selected_models
            }
            
            # Execute the graph
            logger.info("Executing LangGraph workflow...")
            result = await graph.ainvoke(initial_state)
            
            # Extract the final answer
            summary = result.get("final_answer", "")
            retrieved_context = result.get("retrieved_context", [])
            agent_thoughts = result.get("agent_thoughts", [])
            
            logger.info (f"Agent completed with {len(agent_thoughts)} reasoning steps")
            
            # Format individual answers (for backward compatibility)
            answers = {"Agentic": summary}
            
            # Use retrieved context as related knowledge
            related_knowledge = retrieved_context[:5]  # Limit to 5 items
            
        except Exception as e:
            logger.error(f"Agentic RAG error: {e}, falling back to traditional flow")
            # Fall back to traditional flow
            request.use_agentic_rag = False
    
    # Traditional multi-LLM flow (fallback or if use_agentic_rag=False)
    if not request.use_agentic_rag or not os.getenv("OPENAI_API_KEY"):
        logger.info("🔄 Using traditional multi-LLM workflow")
        
        # Get vector search results
        related_knowledge = []
        try:
            async with httpx.AsyncClient() as client:
                vector_response = await client.post(
                    f"{VECTOR_SERVICE_URL}/concepts/search",
                    json={"query": request.user_input, "limit": 3},
                    timeout=30.0
                )
                if vector_response.status_code == 200:
                    vector_data = vector_response.json()
                    related_knowledge = vector_data.get("results", [])
        except Exception as e:
            logger.error(f"Vector service error: {e}")
        
        # Get real AI model responses
        llm_functions = {
            "OpenAI": get_openai_response,
            "Claude": get_claude_response,
            "Gemini": get_gemini_response,
            "Grok": get_grok_response
        }
        
        tasks = [llm_functions[model](request.user_input) for model in request.selected_models if model in llm_functions]
        selected_llms = [model for model in request.selected_models if model in llm_functions]
        
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            answers = {}
            for i, (model, response) in enumerate(zip(selected_llms, responses)):
                if isinstance(response, Exception):
                    answers[model] = f"{model} error: {str(response)[:100]}..."
                else:
                    answers[model] = response
        except Exception as e:
            answers = {model: f"{model} response error" for model in request.selected_models}
        
        # Generate comprehensive summary
        summary = await get_smart_summary(request.user_input, answers)
    
    # Add assistant message to session
    await add_message(session_id, "assistant", summary, metadata={"models_used": request.selected_models})
    
    # Extract topics
    suggested_topics = []
    for item in related_knowledge:
        if "topics" in item:
            suggested_topics.extend(item["topics"])
    current_topics = await _extract_topics_from_question(request.user_input)
    suggested_topics.extend(current_topics)
    suggested_topics = list(set(suggested_topics))[:5]
    
    # Store in database
    try:
        await insert_record(
            user_input=request.user_input,
            answers=answers,
            summary=summary,
            user_id=user.id,
            session_id=session_id  # Link to session
        )
        logger.debug(f"💾 Stored Q&A in PostgreSQL")
    except Exception as e:
        logger.error(f"Error storing knowledge: {e}")
    
    # Store in vector database
    try:
        async with httpx.AsyncClient() as client:
            concept_data = {
                "concepts": [{
                    "id": f"qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user.id[:8]}",
                    "content": f"Q: {request.user_input}\nA: {summary}",
                    "type": "qa_concept",
                    "metadata": {
                        "user_id": user.id,
                        "session_id": session_id,
                        "question": request.user_input,
                        "summary": summary,
                        "topics": suggested_topics,
                        "timestamp": datetime.now().isoformat()
                    }
                }]
            }
            
            await client.post(
                f"{VECTOR_SERVICE_URL}/concepts/add",
                json=concept_data,
                timeout=30.0
            )
    except Exception as e:
        logger.error(f"Error storing in vector database: {e}")
    
    return AskResponse(
        id=session_id,  # Return session_id as the conversation ID
        summary=summary,
        answers=answers if not request.use_agentic_rag else {"Agentic": summary},
        related_knowledge=related_knowledge,
        suggested_topics=suggested_topics
    )
