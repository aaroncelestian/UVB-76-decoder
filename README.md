# 🔊 UVB-76 Live Stream Decoder

A real-time frequency analysis and FSK decoding application for the mysterious UVB-76 "Buzzer" radio station. This application streams live audio from internet radio sources, analyzes frequency patterns, and attempts to decode binary data from the station's FSK (Frequency Shift Keying) transmissions.

## 📡 About UVB-76

UVB-76, also known as "The Buzzer," is a shortwave radio station that broadcasts on 4625 kHz. It has been transmitting a monotonous buzzing sound since the 1970s, occasionally interrupted by voice messages in Russian. This application focuses on analyzing the low-frequency modulation patterns that may carry encoded data.

## ✨ Features

### 🎯 Real-Time Analysis
- **Live Audio Streaming** from multiple internet radio sources
- **Real-Time Frequency Analysis** using FFT with optimized low-frequency resolution
- **FSK State Detection** for three discrete frequency tones (21.53 Hz, 26.92 Hz, 32.30 Hz)
- **Binary Data Extraction** from traditional 2-tone FSK modulation

### 📊 Modern Visualization
- **4-Panel Live Dashboard** with frequency evolution, binary states, waterfall display, and frequency distribution
- **Tabbed Interface** for organized access to stream control, analysis, decoded data, and export functions
- **Real-Time Plotting** with auto-scrolling and zoom capabilities
- **Color-Coded Frequency Regions** for easy identification of data tones vs. carrier

### 🔤 Data Decoding
- **Traditional Binary FSK** (21.53 Hz = 0, 26.92 Hz = 1)
- **Carrier Filtering** (32.30 Hz buzzer periods ignored for cleaner data)
- **Multiple Decode Attempts** (ASCII, decimal, pattern analysis)
- **Pattern Recognition** for repeating sequences and potential message structures

### 💾 Export Capabilities
- **Binary Data Logs** with timestamps and session information
- **Frequency Analysis Data** in CSV format
- **Plot Export** (PNG, PDF, SVG formats)
- **Session Statistics** and comprehensive data export

### 🎤 Audio Recording & 🌊 Waterfall Logging
- **5-Minute Audio Recording** - Automatic WAV file rotation for continuous recording
- **High-Quality Audio** - 44.1kHz, 16-bit mono WAV files with timestamp naming
- **Complete Spectral Data Logging** - Full frequency/magnitude/time data capture
- **Multiple Export Formats** - NPZ (NumPy), PKL (Pickle), and CSV formats
- **Standalone Analysis Tool** - Dedicated waterfall data analysis script
- **Professional Analysis** - Signal strength monitoring, frequency tracking, and pattern detection

## 🚀 Installation

### Requirements
```bash
Python 3.7+
numpy
matplotlib
scipy
requests
tkinter (usually included with Python)
pandas (for data export)
```

### Install Dependencies
```bash
pip install numpy matplotlib scipy requests pandas
```

### Download and Run
```bash
git clone https://github.com/aaroncelestian/UVB-76-decoder.git
cd uvb76-decoder
python uvb76_stream_decoder.py
```

### Additional Files
- **`analyze_waterfall_data.py`** - Standalone waterfall data analysis tool
- **`RECORDING_FEATURES.md`** - Detailed documentation for new recording features
- **`requirements.txt`** - Python dependencies list

## 📖 Usage

### Quick Start
1. **Launch the application**
   ```bash
   python uvb76_stream_decoder.py
   ```

2. **Select a stream source** from the preset URLs or enter your own:
   - WebSDR Netherlands: `http://websdr.ewi.utwente.nl:8901/?tune=4625usb`
   - printf.cc Direct Stream: `http://streams.printf.cc:8000/buzzer.ogg`
   - Or find other UVB-76 streams online

3. **Start streaming** by clicking "🎵 Start Stream"

4. **Monitor the analysis** across four tabs:
   - **Stream Control**: Connection and URL management
   - **Live Analysis**: Real-time frequency and binary state plots
   - **Decoded Data**: Binary stream and pattern analysis
   - **Export & Settings**: Data export, audio recording, and waterfall logging

### Understanding the Output

#### Console Messages
```
FSK Data Tone 1: 21.53 Hz (Binary 0)      ← Actual data transmission
FSK Carrier/Buzzer: 32.30 Hz (Ignored)    ← Standard buzzer (filtered out)
FSK Data Tone 2: 26.92 Hz (Binary 1)      ← Actual data transmission
```

#### Decoded Data Tab
- **Binary Data**: Clean 0s and 1s from actual FSK modulation
- **Data Tone Distribution**: Statistics on frequency usage
- **ASCII/Decimal Attempts**: Automatic decoding attempts
- **Pattern Analysis**: Detection of repeating sequences

#### Frequency Distribution Plot
- **Red Region**: 21.53 Hz ± tolerance (Binary 0)
- **Green Region**: 26.92 Hz ± tolerance (Binary 1)
- **Gray Region**: 32.30 Hz ± tolerance (Carrier/Buzzer - ignored)

### 🎤 Audio Recording Features

#### Continuous Recording
1. **Start Recording**: Click "🎤 Start Recording" in Export & Settings tab
2. **Automatic Rotation**: New WAV file created every 5 minutes
3. **Professional Quality**: 44.1kHz, 16-bit mono audio
4. **Smart Naming**: `uvb76_recording_YYYYMMDD_HHMMSS_001.wav`
5. **File Organization**: All recordings saved to `recordings/` directory

#### Benefits
- **Complete Audio Archive**: Never miss a transmission
- **High-Quality Preservation**: Suitable for detailed analysis
- **Manageable File Sizes**: ~25-30MB per 5-minute segment
- **Automated Management**: No manual intervention required

### 🌊 Waterfall Data Logging

#### Spectral Data Capture
1. **Start Logging**: Click "📈 Start Logging" in Detailed Spectral Logging section
2. **Complete Data**: Captures frequency, magnitude, timestamps, and metadata
3. **Export Options**: Choose NPZ (recommended), PKL, or CSV format
4. **Analysis Ready**: Data optimized for scientific analysis

#### Standalone Analysis Tool
Use the included `analyze_waterfall_data.py` for advanced analysis:

```bash
# Basic waterfall visualization
python analyze_waterfall_data.py waterfall_data.npz

# Focus on UVB-76 frequency range
python analyze_waterfall_data.py data.npz --freq-range 20 35

# Analyze specific frequency over time
python analyze_waterfall_data.py data.npz --target-freq 26.92 --save-plot

# Generate analysis report
python analyze_waterfall_data.py data.npz --export-summary
```

#### Data Analysis Capabilities
- **Signal Strength Monitoring**: Track amplitude changes over time
- **Frequency Tracking**: Monitor frequency stability and shifts
- **Pattern Detection**: Identify transmission patterns and anomalies
- **Publication-Quality Plots**: Export professional visualizations

## 🔬 Technical Details

### FSK Analysis Method
The application uses a **traditional 2-tone FSK decoding approach**:

1. **Audio Processing**: 8192-sample windows with Hann windowing
2. **FFT Analysis**: Optimized for low-frequency resolution (20-35 Hz range)
3. **Peak Detection**: Identifies strongest frequency components above threshold
4. **State Classification**: Maps frequencies to binary states with tolerance
5. **Carrier Filtering**: Excludes 32.30 Hz periods to isolate message data

### Frequency Mapping
Based on real UVB-76 frequency analysis:
- **21.53 Hz** → Binary 0 (Data Tone 1)
- **26.92 Hz** → Binary 1 (Data Tone 2)
- **32.30 Hz** → Carrier/Buzzer (Ignored)

### Signal Processing Parameters
- **Sample Rate**: 44.1 kHz (typical for internet streams)
- **Window Size**: 8192 samples (~185ms at 44.1kHz)
- **Frequency Resolution**: ~5.4 Hz
- **Detection Threshold**: 15.0 magnitude units
- **Frequency Tolerance**: ±0.5 Hz for classification

## 📈 Data Export

### Binary Log Format
```csv
timestamp,session_time,binary_state,frequency,bit_number
1640995200.123,0.5,0,21.53,1
1640995200.345,0.7,1,26.92,2
```

### Frequency Log Format
```csv
timestamp,session_time,frequency,magnitude,audio_level
1640995200.123,0.5,21.53,45.2,0.4978
```

### Audio Recording Files
```
recordings/
├── uvb76_recording_20241201_143022_001.wav  (First 5-minute segment)
├── uvb76_recording_20241201_143522_002.wav  (Second 5-minute segment)
└── uvb76_recording_20241201_144022_003.wav  (Third 5-minute segment)
```

### Waterfall Data Formats

#### NPZ Format (Recommended)
```python
# Load waterfall data
import numpy as np
data = np.load('waterfall_data.npz', allow_pickle=True)
timestamps = data['timestamps']      # Unix timestamps
magnitudes = data['magnitudes']      # 2D array [time, frequency]
frequencies = data['frequencies']    # Frequency bins (Hz)
metadata = data['metadata'].item()   # Session information
```

#### Analysis Usage
```python
# Create waterfall visualization
import matplotlib.pyplot as plt
plt.imshow(np.log10(magnitudes), aspect='auto', 
           extent=[frequencies[0], frequencies[-1], 
                  timestamps[-1], timestamps[0]])
plt.xlabel('Frequency (Hz)')
plt.ylabel('Time (s)')
plt.colorbar(label='Magnitude (log10)')
plt.show()
```

## 🛠️ Troubleshooting

### Common Issues

**No Audio Data**
- Verify internet connection
- Try different stream URLs
- Check if stream is currently active
- Some streams may require specific audio codecs

**No Binary Data in Decoded Tab**
- UVB-76 may be in carrier-only mode (normal)
- Data transmissions are rare and brief
- Ensure stream is actually UVB-76 frequency
- Check console for FSK state detection messages

**Plot Update Issues**
- Reduce plot update frequency if performance is poor
- Close other resource-intensive applications
- Try smaller window sizes for lower-end systems

### Stream Sources
If preset URLs don't work, search for:
- "UVB-76 live stream"
- "4625 kHz WebSDR"
- "Buzzer station online"
- KiwiSDR stations tuned to 4.625 MHz

## 🎯 Understanding UVB-76 Behavior

### Normal Operation
- **95% of time**: Constant 32.30 Hz buzzer tone
- **Rare events**: Brief FSK modulation during message transmission
- **Very rare events**: Voice announcements in Russian

### What to Expect
- Long periods of no binary data (normal buzzer operation)
- Occasional bursts of 0s and 1s during active transmission
- Most "data" may be synchronization or test patterns
- Actual message content is extremely rare

## 📚 Background

This decoder is based on analysis of real UVB-76 transmissions and aims to:
1. Monitor for rare data transmission events
2. Analyze the station's modulation characteristics
3. Provide tools for signal intelligence research
4. Document patterns in this mysterious radio station

The application uses scientifically rigorous signal processing methods and has been validated against known UVB-76 frequency characteristics.

## ⚠️ Disclaimer

This application is for educational and research purposes only. UVB-76 is believed to be operated by the Russian military. Users should comply with all applicable laws regarding radio monitoring in their jurisdiction.

## 🤝 Contributing

Contributions welcome! Areas of interest:
- Additional demodulation algorithms
- Pattern recognition improvements
- New stream source integration
- Enhanced visualization features
- Improved message decoding methods

## 📄 License

MIT

---

**Made for radio enthusiasts, researchers, and the mysteriously curious** 📻✨ 