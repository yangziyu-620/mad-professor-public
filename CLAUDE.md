# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mad Professor (暴躁的教授读论文) is an academic paper reading companion application that enhances the paper reading experience through an AI assistant with a distinctive "mad professor" personality. It helps researchers read, understand, and analyze academic papers more efficiently.

## Key Commands

### Environment Setup
```bash
# Create conda environment
conda create -n mad-professor python=3.10.16
conda activate mad-professor

# Install MinerU dependency first
pip install -U magic-pdf[full]==1.3.3 -i https://mirrors.aliyun.com/pypi/simple

# Install remaining dependencies
pip install -r requirements.txt

# Install CUDA-compatible torch (adjust version based on your GPU)
pip install --force-reinstall torch torchvision torchaudio "numpy<=2.1.1" --index-url https://download.pytorch.org/whl/cu124

# Install FAISS GPU version (only via conda)
conda install -c conda-forge faiss-gpu

# Download models
python download_models.py
```

### Running the Application
```bash
# Windows
start.bat
# or directly
python main.py
```

### Development Commands
- No specific linting, testing, or formatting commands are configured in this project
- Follow the "minimal modification principle" - preserve existing functionality when adding new features
- Check library documentation before making changes, matching library and documentation versions

## Code Architecture

### Core System Flow
1. **PDF Import** → `pipeline.py` orchestrates the processing
2. **PDF Processing** → `processor/pdf_processor.py` converts PDF to Markdown using MinerU
3. **Translation** → `processor/translate_processor.py` translates content (Chinese ↔ English)
4. **Structuring** → `processor/json_processor.py` creates structured JSON representation
5. **RAG Index** → `processor/rag_processor.py` builds vector embeddings using FAISS
6. **UI Display** → `AI_professor_UI.py` presents content with dual-language support
7. **AI Interaction** → `AI_professor_chat.py` handles Q&A with professor personality

### Key Components
- **AI Manager** (`AI_manager.py`): Centralizes all AI functionality
- **RAG System** (`rag_retriever.py`): Vector search for precise paper content retrieval
- **Data Manager** (`data_manager.py`): Manages paper indices and content loading
- **Voice System**: `voice_input.py` (STT) + `TTS_manager.py` (TTS)
- **Threading** (`threads.py`): Handles async operations for UI responsiveness

### Important Directories
- `data/`: Source PDFs (input)
- `output/`: Processed papers (JSONs, translations, RAG indices)
- `models/`: Downloaded AI models
- `prompt/`: AI personality prompts and function-specific prompts
- `ui/`: PyQt6 UI components
- `processor/`: Processing pipeline modules

## Development Guidelines

### API Configuration
- API keys are managed via `api_config.json` (auto-generated from template on first run)
- Supports multiple LLM providers: xAI, OpenRouter, DeepSeek, Anthropic, OpenAI
- TTS uses MiniMax API for voice synthesis

### Model Management
- Models are downloaded via `python download_models.py`
- Configuration stored in user directory's `magic-pdf.json`
- Whisper model downloads automatically on first voice input use

### Key Development Principles (from Cursor rules)
1. **Minimal Modification**: Always preserve existing functionality when adding new features
2. **Documentation First**: Check library documentation before modifications
3. **Version Matching**: Ensure library and documentation versions match

### Adding New Features
- New AI personalities: Add prompt file in `prompt/ai_character_prompt_[name].txt`
- New processors: Add to `processor/` directory and integrate via `pipeline.py`
- UI components: Add to `ui/` directory following PyQt6 patterns

## Common Tasks

### Processing New Papers
1. Place PDF in `data/` directory or use the import button in UI
2. System automatically detects and processes unprocessed PDFs
3. Processing includes: PDF→MD conversion, translation, JSON structuring, RAG indexing

### Modifying AI Personality
1. Create new prompt file: `prompt/ai_character_prompt_[name].txt`
2. Update `AI_CHARACTER_PROMPT_PATH` in `AI_professor_chat.py`
3. For voice changes, modify `voice_id` in `TTS_manager.py`

### Debugging Processing Pipeline
- Check `output/` directory for intermediate processing results
- Each paper has subdirectories for different processing stages
- Log files and error messages are typically printed to console

## Technical Notes

### Dependencies
- **MinerU**: PDF to Markdown conversion (requires specific version 1.3.3)
- **RealtimeSTT**: Real-time speech recognition
- **FAISS-GPU**: Vector search (requires conda installation)
- **PyQt6**: Desktop GUI framework
- **LangChain**: LLM orchestration

### GPU Requirements
- Minimum 6GB VRAM
- CUDA support required
- Configure `device-mode: "cuda"` in user's `magic-pdf.json`

### Known Limitations
- Optimized for academic paper PDFs only
- Voice input may capture AI's own speech when using speakers (use headphones)
- Processing large PDFs may take significant time