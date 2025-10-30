# Quick Start: Using Your Custom Model

This guide gets you up and running with your custom Ollama model in under 5 minutes.

## What Was Fixed

Your custom model was generating test code instead of normal conversation because the prompts were too strict and confusing. We've fixed that! 🎉

## Quick Setup (3 Steps)

### 1. Set Your Model Name

```bash
export AGENT_MODEL=your-model-name
```

Replace `your-model-name` with the actual name from `ollama list`.

### 2. Test It (Optional but Recommended)

```bash
python test_llm_response.py
```

This validates your model responds correctly to both chat and tool requests.

### 3. Run the Application

```bash
python -m src.app
# Or using make:
make run
```

## Expected Behavior Now

✅ **Simple chat works naturally:**
```
You: Hello
Agent: Hello! How can I help you today?
```

✅ **Tool calls work when needed:**
```
You: Search the web for Python tutorials
Agent: [Uses webbrowser tool to search]
```

✅ **No more unwanted code generation:**
- The agent won't generate test code unless you explicitly ask
- It responds conversationally by default
- Tools are only used when actually needed

## Troubleshooting

### "Model not found"
```bash
# Check your model exists
ollama list

# Make sure the name matches exactly
export AGENT_MODEL=exact-model-name-from-list
```

### Still getting weird responses?
1. Make sure you're using the latest code (this PR)
2. Try restarting Ollama: `pkill ollama && ollama serve`
3. Check your model is appropriate (7B+ parameters recommended)
4. See the detailed guide: `CUSTOM_MODEL_GUIDE.md`

### Model not calling tools when it should?
This is normal for some models. The improved prompts accept this gracefully - the agent will explain what it would do instead of failing.

## What Changed Technically

1. **Better Prompts**: Clear guidance on when to chat vs when to use tools
2. **Configurable Model**: Use `AGENT_MODEL` env var instead of editing code
3. **Conversational First**: Agent prioritizes natural conversation over tool usage

## More Information

- **Full guide**: See `CUSTOM_MODEL_GUIDE.md`
- **All changes**: See `CHANGES_SUMMARY.md`
- **Test script**: Run `python test_llm_response.py`

## Permanent Setup

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export AGENT_MODEL=your-model-name
```

Or create a `.env` file in the project root (you'll need to add python-dotenv support for this to work automatically).

## Need Help?

1. Check `CUSTOM_MODEL_GUIDE.md` for detailed troubleshooting
2. Run the test script to diagnose issues: `python test_llm_response.py`
3. Verify Ollama is running: `curl http://localhost:11434/api/tags`

---

**That's it!** Your custom model should now chat naturally and use tools appropriately. 🚀
