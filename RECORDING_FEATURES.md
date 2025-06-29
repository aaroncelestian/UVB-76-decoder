# UVB-76 Audio Recording & Waterfall Data Logging

This document describes the new audio recording and waterfall data logging features added to the UVB-76 Stream Decoder.

## New Features

### 1. Audio Recording with 5-Minute Rotation

The decoder can now record the streamed audio to WAV files with automatic rotation every 5 minutes.

**Features:**
- Records raw audio stream to high-quality WAV files
- Automatically creates new files every 5 minutes
- Files are saved in `recordings/` directory
- Timestamp-based naming: `uvb76_recording_YYYYMMDD_HHMMSS_001.wav`
- Automatic cleanup when streaming stops

**How to Use:**
1. Start streaming audio
2. Go to "Export & Settings" tab
3. Click "🎤 Start Recording" in the Audio Recording section
4. Recording status will show "Recording to WAV files..."
5. Click "⏹️ Stop Recording" to stop

**File Format:**
- Format: WAV (uncompressed)
- Channels: Mono (1 channel)
- Sample Rate: 44.1 kHz
- Bit Depth: 16-bit
- Typical file size: ~25-30 MB per 5-minute file

### 2. Enhanced Waterfall Data Logging

The decoder now supports detailed spectral data logging for future analysis.

**Features:**
- Logs complete frequency/magnitude data for each time sample
- Stores frequency axis, magnitudes, timestamps, and metadata
- Exports in multiple formats (NPZ, PKL, CSV)
- Optimized for spectral analysis workflows

**How to Use:**
1. Go to "Export & Settings" tab
2. Click "📈 Start Logging" in the Detailed Spectral Logging section
3. Status will show "Logging spectral data..."
4. Click "🌊 Waterfall Data" to export logged data
5. Choose format:
   - **NPZ**: Recommended for Python analysis (compressed)
   - **PKL**: Python pickle format (includes all metadata)
   - **CSV**: Human-readable format (larger files)

## Data Analysis

### Using the Waterfall Analysis Tool

A standalone analysis tool is included: `analyze_waterfall_data.py`

**Basic Usage:**
```bash
python analyze_waterfall_data.py waterfall_data.npz
```

**Advanced Options:**
```bash
# Analyze specific frequency range (20-35 Hz)
python analyze_waterfall_data.py data.npz --freq-range 20 35

# Analyze specific time window (first 300 seconds)
python analyze_waterfall_data.py data.npz --time-range 0 300

# Focus on specific frequency and save plot
python analyze_waterfall_data.py data.npz --target-freq 26.92 --save-plot

# Export summary report
python analyze_waterfall_data.py data.npz --export-summary
```

### Loading Data in Python

```python
import numpy as np
import matplotlib.pyplot as plt

# Load NPZ file
data = np.load('waterfall_data.npz', allow_pickle=True)
timestamps = data['timestamps']
magnitudes = data['magnitudes']
frequencies = data['frequencies']
metadata = data['metadata'].item()

# Create waterfall plot
plt.figure(figsize=(12, 8))
plt.imshow(np.log10(magnitudes), aspect='auto', 
           extent=[frequencies[0], frequencies[-1], 
                  timestamps[-1], timestamps[0]])
plt.xlabel('Frequency (Hz)')
plt.ylabel('Time (s)')
plt.title('UVB-76 Waterfall')
plt.colorbar(label='Magnitude (log10)')
plt.show()
```

## File Organization

```
recordings/
├── uvb76_recording_20241201_143022_001.wav  (First 5-minute segment)
├── uvb76_recording_20241201_143522_002.wav  (Second 5-minute segment)
└── uvb76_recording_20241201_144022_003.wav  (Third 5-minute segment)

exported_data/
├── uvb76_waterfall_20241201_144500.npz      (Spectral data)
├── uvb76_session_20241201_144500_binary.csv (Binary data)
├── uvb76_session_20241201_144500_frequency.csv (Frequency data)
└── waterfall_analysis_20241201_145000.txt   (Analysis summary)
```

## Data Formats

### NPZ Format (Recommended)
```python
# Contains:
timestamps      # Array of Unix timestamps
magnitudes      # 2D array [time, frequency] of magnitudes
frequencies     # 1D array of frequency bins (Hz)
sample_rates    # Sample rate for each time sample
audio_levels    # Audio level for each time sample
metadata        # Dict with session info
```

### Analysis Capabilities

1. **Signal Strength Analysis**
   - Peak frequency detection
   - UVB-76 frequency monitoring (21.53, 26.92, 32.30 Hz)
   - Time series analysis

2. **Spectral Analysis**
   - Waterfall visualization
   - Average spectrum calculation
   - Frequency domain filtering

3. **Pattern Detection**
   - Signal activity periods
   - Frequency shift detection
   - Correlation analysis

## Performance Notes

- **Audio Recording**: Minimal performance impact, ~30 MB per 5 minutes
- **Basic Waterfall**: Low memory usage, suitable for long sessions
- **Detailed Logging**: Higher memory usage (~1000 entries max), use for focused analysis
- **Export Speed**: NPZ format is fastest, CSV is slowest but most compatible

## Tips for Analysis

1. **For FSK Analysis**: Focus on 20-35 Hz range with detailed logging
2. **For Long Sessions**: Use basic waterfall + audio recording
3. **For Python Analysis**: Use NPZ format with the analysis tool
4. **For Other Tools**: Export CSV format for maximum compatibility

## Troubleshooting

**Audio Recording Issues:**
- Ensure `recordings/` directory is writable
- Check available disk space (30 MB per 5 minutes)
- Verify stream is providing audio data

**Waterfall Export Issues:**
- Stop detailed logging before export for large datasets
- Use NPZ format for files >100 MB
- Check memory usage with detailed logging enabled

**Analysis Tool Issues:**
- Install required packages: `numpy`, `matplotlib`, `pandas`
- Use `--freq-range` to reduce memory usage for large files
- Check file format matches expected structure 