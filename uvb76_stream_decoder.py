#!/usr/bin/env python3
"""
UVB-76 Live Stream Decoder
Real-time frequency state decoding from internet radio streams
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import requests
import threading
import queue
import time
from collections import deque
from scipy import signal
from scipy.fft import fft, fftfreq
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import io

class UVB76StreamDecoder:
    def __init__(self):
        self.sample_rate = 44100
        self.chunk_size = 4096
        self.is_streaming = False
        self.audio_queue = queue.Queue()
        self.frequency_buffer = deque(maxlen=1000)  # Store last 1000 frequency measurements
        self.binary_buffer = deque(maxlen=500)     # Store decoded binary states
        self.time_buffer = deque(maxlen=1000)
        self.audio_level_buffer = deque(maxlen=1000)  # Store audio levels for diagnostics
        
        # Logging and data storage
        self.binary_log = []  # Complete binary log with timestamps
        self.frequency_log = []  # Complete frequency log
        self.waterfall_log = []  # Complete waterfall data storage
        self.session_start_time = None
        
        # Stream diagnostics
        self.bytes_received = 0
        self.chunks_processed = 0
        self.last_audio_time = 0
        
        # Real UVB-76 FSK frequencies from data analysis
        # These are the actual discrete frequencies found in live data
        self.uvb76_frequencies = {
            'freq_1': 21.53,  # First FSK tone
            'freq_2': 26.92,  # Second FSK tone  
            'freq_3': 32.30   # Third FSK tone (most common - likely buzzer/carrier)
        }
        
        # Tolerance for frequency matching (±0.5 Hz)
        self.freq_tolerance = 0.5
        
        # Magnitude thresholds based on real data analysis (20-70 range observed)
        self.min_signal_strength = 15.0  # Minimum magnitude to consider
        self.strong_signal_threshold = 45.0  # Strong signal threshold
        
        # FSK state tracking
        self.current_fsk_state = None
        self.last_fsk_change = None
        self.fsk_state_history = deque(maxlen=50)  # Track recent FSK states
        
        self.stream_thread = None
        self.analysis_thread = None
        
    def create_gui(self):
        """Create the modern streaming decoder GUI with tabbed interface"""
        
        self.root = tk.Tk()
        self.root.title("🔊 UVB-76 Live Stream Decoder")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')
        
        # Configure modern styling
        style = ttk.Style()
        style.theme_use('clam')
        
        # Custom colors for modern look
        style.configure('Title.TLabel', font=('Arial', 18, 'bold'), foreground='#2c3e50')
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), foreground='#34495e')
        style.configure('Status.TLabel', font=('Arial', 10), foreground='#7f8c8d')
        style.configure('Success.TLabel', font=('Arial', 10), foreground='#27ae60')
        style.configure('Error.TLabel', font=('Arial', 10), foreground='#e74c3c')
        
        # Main container with padding
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header section
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Title with icon
        title_label = ttk.Label(header_frame, text="📡 UVB-76 Live Stream Frequency Decoder", 
                               style='Title.TLabel')
        title_label.pack(side=tk.LEFT)
        
        # Status indicator in header
        self.connection_status = ttk.Label(header_frame, text="●", foreground='#95a5a6', 
                                          font=('Arial', 16))
        self.connection_status.pack(side=tk.RIGHT, padx=(0, 10))
        
        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Stream Controls
        self.create_stream_tab()
        
        # Tab 2: Live Analysis  
        self.create_analysis_tab()
        
        # Tab 3: Decoded Data
        self.create_data_tab()
        
        # Tab 4: Export & Settings
        self.create_export_tab()
        
        # Status bar at bottom
        self.create_status_bar(main_container)
        
        # Initialize plot updates
        self.plot_update_timer = None
        self.start_plot_updates()
        
        return self.root
    
    def create_stream_tab(self):
        """Create the stream control tab"""
        stream_tab = ttk.Frame(self.notebook)
        self.notebook.add(stream_tab, text="🌐 Stream Control")
        
        # Main stream controls section
        controls_frame = ttk.LabelFrame(stream_tab, text="Stream Configuration", padding=20)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # URL input section
        url_frame = ttk.Frame(controls_frame)
        url_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(url_frame, text="Stream URL:", style='Heading.TLabel').pack(anchor=tk.W)
        
        url_input_frame = ttk.Frame(url_frame)
        url_input_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.stream_url = tk.StringVar(value="http://websdr.ewi.utwente.nl:8901/m.mp3?f=4625")
        self.stream_entry = ttk.Entry(url_input_frame, textvariable=self.stream_url, 
                                     font=('Consolas', 10), width=80)
        self.stream_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.stream_btn = ttk.Button(url_input_frame, text="🎵 Start Stream", 
                                    command=self.toggle_stream, width=15)
        self.stream_btn.pack(side=tk.RIGHT)
        
        # Preset URLs section
        presets_frame = ttk.LabelFrame(controls_frame, text="Quick Access URLs", padding=15)
        presets_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Create a grid of preset buttons
        presets = [
            ("WebSDR Netherlands", "http://websdr.ewi.utwente.nl:8901/?tune=4625usb", "#3498db"),
            ("printf.cc Direct Stream", "http://streams.printf.cc:8000/buzzer.ogg", "#e67e22"),
            ("printf.cc WebSDR", "http://websdr.printf.cc:8901/?tune=4625usb", "#9b59b6"),
            ("Local Test File", "file://test_recording.wav", "#95a5a6")
        ]
        
        preset_grid = ttk.Frame(presets_frame)
        preset_grid.pack(fill=tk.X)
        
        for i, (name, url, color) in enumerate(presets):
            row = i // 2
            col = i % 2
            
            btn_frame = ttk.Frame(preset_grid)
            btn_frame.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
            
            btn = ttk.Button(btn_frame, text=name, width=30,
                           command=lambda u=url: self.set_stream_url(u))
            btn.pack(fill=tk.X)
            
            # URL preview label
            url_preview = ttk.Label(btn_frame, text=url[:50] + "..." if len(url) > 50 else url,
                                   font=('Consolas', 8), foreground='#7f8c8d')
            url_preview.pack(fill=tk.X, pady=(2, 0))
        
        # Configure grid weights
        preset_grid.columnconfigure(0, weight=1)
        preset_grid.columnconfigure(1, weight=1)
        
        # Stream status section
        status_frame = ttk.LabelFrame(stream_tab, text="Connection Status", padding=20)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Connection info display
        info_grid = ttk.Frame(status_frame)
        info_grid.pack(fill=tk.X)
        
        # Status text
        ttk.Label(info_grid, text="Status:", style='Heading.TLabel').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.status_var = tk.StringVar(value="Ready to stream")
        self.status_label = ttk.Label(info_grid, textvariable=self.status_var, style='Status.TLabel')
        self.status_label.grid(row=0, column=1, sticky='w')
        
        # Data received
        ttk.Label(info_grid, text="Data Received:", style='Heading.TLabel').grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
        self.data_received_var = tk.StringVar(value="0 KB")
        ttk.Label(info_grid, textvariable=self.data_received_var, style='Status.TLabel').grid(row=1, column=1, sticky='w', pady=(5, 0))
        
        # Session time
        ttk.Label(info_grid, text="Session Time:", style='Heading.TLabel').grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
        self.session_time_var = tk.StringVar(value="00:00:00")
        ttk.Label(info_grid, textvariable=self.session_time_var, style='Status.TLabel').grid(row=2, column=1, sticky='w', pady=(5, 0))
        
        # Current FSK State
        ttk.Label(info_grid, text="FSK State:", style='Heading.TLabel').grid(row=3, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
        self.fsk_state_var = tk.StringVar(value="Waiting...")
        ttk.Label(info_grid, textvariable=self.fsk_state_var, style='Status.TLabel').grid(row=3, column=1, sticky='w', pady=(5, 0))
    
    def create_analysis_tab(self):
        """Create the live analysis visualization tab"""
        analysis_tab = ttk.Frame(self.notebook)
        self.notebook.add(analysis_tab, text="📈 Live Analysis")
        
        # Create matplotlib figure with compact but readable fonts
        plt.style.use('default')  # Reset to default style
        plt.rcParams.update({
            'font.size': 6,            # Compact base font
            'axes.titlesize': 7,       # Compact titles
            'axes.labelsize': 6,       # Compact axis labels
            'xtick.labelsize': 5,      # Compact tick labels
            'ytick.labelsize': 5,      # Compact tick labels
            'legend.fontsize': 5,      # Compact legend
            'figure.facecolor': 'white',
            'axes.facecolor': 'white'
        })
        
        self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 7))
        self.fig.suptitle('UVB-76 Live Frequency Analysis', fontsize=9, fontweight='bold')
        # Use subplots_adjust for more precise control over spacing
        self.fig.subplots_adjust(
            left=0.08,      # Left margin
            right=0.95,     # Right margin  
            top=0.88,       # Top margin (below title)
            bottom=0.08,    # Bottom margin
            hspace=0.4,     # Vertical spacing between rows - good balance
            wspace=0.25     # Horizontal spacing between columns - more compact
        )
        
        # Waterfall data storage
        self.waterfall_data = []
        self.waterfall_times = []
        self.max_waterfall_lines = 100
        
        # Initialize plots with better styling
        
        # Top Left: Frequency evolution
        self.line_freq, = self.axes[0, 0].plot([], [], 'b-', linewidth=1.5)
        self.axes[0, 0].set_title('Frequency Evolution (Live)')
        self.axes[0, 0].set_xlabel('Time (seconds)')
        self.axes[0, 0].set_ylabel('Frequency (Hz)')
        self.axes[0, 0].grid(True, alpha=0.3)
        self.axes[0, 0].set_ylim(18, 35)
        
        # Add frequency state regions with better colors
        self.axes[0, 0].axhspan(20, 23, alpha=0.2, color='#e74c3c', label='Binary 0')
        self.axes[0, 0].axhspan(23, 26, alpha=0.2, color='#f39c12', label='Carrier')
        self.axes[0, 0].axhspan(26, 30, alpha=0.2, color='#27ae60', label='Binary 1')
        self.axes[0, 0].axhspan(30, 35, alpha=0.2, color='#95a5a6', label='Out of Range')
        self.axes[0, 0].legend(loc='upper right')
        
        # Top Right: Binary states
        self.line_binary, = self.axes[0, 1].plot([], [], 'ro-', markersize=3, linewidth=1.5)
        self.axes[0, 1].set_title('Decoded Binary States')
        self.axes[0, 1].set_xlabel('Time (seconds)')
        self.axes[0, 1].set_ylabel('Binary State')
        self.axes[0, 1].set_ylim(-0.5, 1.5)
        self.axes[0, 1].set_yticks([0, 1])
        self.axes[0, 1].set_yticklabels(['0', '1'])
        self.axes[0, 1].grid(True, alpha=0.3)
        
        # Bottom Left: Waterfall
        self.axes[1, 0].set_title('Real-time Waterfall (0-100 Hz)')
        self.axes[1, 0].set_xlabel('Frequency (Hz)')
        self.axes[1, 0].set_ylabel('Time (recent)')
        
        # Bottom Right: Frequency histogram
        self.axes[1, 1].set_title('Frequency Distribution')
        self.axes[1, 1].set_xlabel('Frequency (Hz)')
        self.axes[1, 1].set_ylabel('Count')
        self.axes[1, 1].set_xlim(18, 35)
        
        # Embed matplotlib in tkinter with better space utilization
        canvas_frame = ttk.Frame(analysis_tab)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.canvas = FigureCanvasTkAgg(self.fig, canvas_frame)
        self.canvas.draw()
        # Use available space efficiently but with reasonable constraints
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        # Add toolbar for plot interaction
        try:
            toolbar_frame = ttk.Frame(canvas_frame)
            toolbar_frame.pack(fill=tk.X, pady=(5, 0))
            
            from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
            toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            toolbar.update()
        except ImportError:
            # Toolbar not available, skip it
            pass
    
    def create_data_tab(self):
        """Create the decoded data display tab"""
        data_tab = ttk.Frame(self.notebook)
        self.notebook.add(data_tab, text="🔤 Decoded Data")
        
        # Create paned window for resizable sections
        paned = ttk.PanedWindow(data_tab, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Binary stream section
        binary_frame = ttk.LabelFrame(paned, text="Binary Stream", padding=10)
        paned.add(binary_frame, weight=1)
        
        # Controls for binary display
        binary_controls = ttk.Frame(binary_frame)
        binary_controls.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(binary_controls, text="Binary Data Stream:", 
                 style='Heading.TLabel').pack(side=tk.LEFT)
        
        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(binary_controls, text="Auto-scroll", 
                       variable=self.auto_scroll_var).pack(side=tk.RIGHT)
        
        # Binary text display with better formatting
        self.binary_text = scrolledtext.ScrolledText(binary_frame, height=8, 
                                                    font=('Consolas', 11), 
                                                    state='disabled',
                                                    wrap=tk.WORD)
        self.binary_text.pack(fill=tk.BOTH, expand=True)
        
        # Pattern analysis section
        pattern_frame = ttk.LabelFrame(paned, text="Pattern Analysis & Decoding", padding=10)
        paned.add(pattern_frame, weight=1)
        
        # Pattern analysis controls
        pattern_controls = ttk.Frame(pattern_frame)
        pattern_controls.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(pattern_controls, text="Message Interpretation:", 
                 style='Heading.TLabel').pack(side=tk.LEFT)
        
        # Clear button
        ttk.Button(pattern_controls, text="Clear", 
                  command=self.clear_pattern_display).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Export button
        ttk.Button(pattern_controls, text="Export", 
                  command=self.export_decoded_data).pack(side=tk.RIGHT)
        
        # Pattern text display
        self.pattern_text = scrolledtext.ScrolledText(pattern_frame, height=10,
                                                     font=('Consolas', 10),
                                                     state='disabled',
                                                     wrap=tk.WORD)
        self.pattern_text.pack(fill=tk.BOTH, expand=True)
    
    def create_export_tab(self):
        """Create the export and settings tab"""
        export_tab = ttk.Frame(self.notebook)
        self.notebook.add(export_tab, text="💾 Export & Settings")
        
        # Logging settings section
        logging_frame = ttk.LabelFrame(export_tab, text="Real-time Logging Settings", padding=15)
        logging_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(logging_frame, text="Enable logging for:", style='Heading.TLabel').pack(anchor=tk.W, pady=(0, 10))
        
        # Logging checkboxes in a nice grid
        log_grid = ttk.Frame(logging_frame)
        log_grid.pack(fill=tk.X)
        
        self.log_binary_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(log_grid, text="📊 Binary Data Log", 
                       variable=self.log_binary_var).grid(row=0, column=0, sticky='w', padx=(0, 20))
        
        self.log_frequency_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(log_grid, text="📈 Frequency Data Log", 
                       variable=self.log_frequency_var).grid(row=0, column=1, sticky='w')
        
        self.log_waterfall_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(log_grid, text="🌊 Waterfall Data Log (Large files)", 
                       variable=self.log_waterfall_var).grid(row=1, column=0, sticky='w', pady=(5, 0), columnspan=2)
        
        # Export section
        export_frame = ttk.LabelFrame(export_tab, text="Export Data", padding=15)
        export_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Figure export
        fig_frame = ttk.Frame(export_frame)
        fig_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(fig_frame, text="Export Plots:", style='Heading.TLabel').pack(anchor=tk.W, pady=(0, 5))
        
        fig_buttons = ttk.Frame(fig_frame)
        fig_buttons.pack(fill=tk.X)
        
        ttk.Button(fig_buttons, text="📸 PNG", command=self.save_figure_png, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fig_buttons, text="📄 PDF", command=self.save_figure_pdf, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fig_buttons, text="🎨 SVG", command=self.save_figure_svg, width=12).pack(side=tk.LEFT)
        
        # Data export
        data_frame = ttk.Frame(export_frame)
        data_frame.pack(fill=tk.X)
        
        ttk.Label(data_frame, text="Export Raw Data:", style='Heading.TLabel').pack(anchor=tk.W, pady=(0, 5))
        
        data_buttons = ttk.Frame(data_frame)
        data_buttons.pack(fill=tk.X)
        
        ttk.Button(data_buttons, text="🔤 Binary Log", command=self.export_binary_log, width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(data_buttons, text="📊 Frequency Data", command=self.export_frequency_log, width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(data_buttons, text="📦 All Data", command=self.export_all_data, width=15).pack(side=tk.LEFT)
        
        # Session info section
        session_frame = ttk.LabelFrame(export_tab, text="Session Information", padding=15)
        session_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.session_info_var = tk.StringVar(value="No active session")
        session_info_label = ttk.Label(session_frame, textvariable=self.session_info_var, 
                                      style='Status.TLabel', wraplength=600)
        session_info_label.pack(anchor=tk.W)
        
        # Statistics display
        stats_text = scrolledtext.ScrolledText(session_frame, height=8, 
                                              font=('Consolas', 9), 
                                              state='disabled')
        stats_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.stats_text = stats_text
    
    def create_status_bar(self, parent):
        """Create a modern status bar at the bottom"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Separator line
        ttk.Separator(status_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 5))
        
        status_content = ttk.Frame(status_frame)
        status_content.pack(fill=tk.X, padx=5, pady=5)
        
        # Connection indicator
        self.connection_indicator = ttk.Label(status_content, text="⚫ Disconnected", 
                                            foreground='#95a5a6')
        self.connection_indicator.pack(side=tk.LEFT)
        
        # Data rate
        self.data_rate_var = tk.StringVar(value="0 KB/s")
        ttk.Label(status_content, text="│").pack(side=tk.LEFT, padx=10)
        ttk.Label(status_content, textvariable=self.data_rate_var).pack(side=tk.LEFT)
        
        # Frequency state
        self.freq_state_var = tk.StringVar(value="No signal")
        ttk.Label(status_content, text="│").pack(side=tk.LEFT, padx=10)
        ttk.Label(status_content, text="Frequency:").pack(side=tk.LEFT)
        ttk.Label(status_content, textvariable=self.freq_state_var).pack(side=tk.LEFT, padx=(5, 0))
        
        # Version info
        ttk.Label(status_content, text="v1.0").pack(side=tk.RIGHT, padx=(10, 0))
    
    def clear_pattern_display(self):
        """Clear the pattern analysis display"""
        self.pattern_text.config(state='normal')
        self.pattern_text.delete(1.0, tk.END)
        self.pattern_text.config(state='disabled')
    
    def export_decoded_data(self):
        """Export decoded data from the data tab"""
        # This would export the current decoded data
        messagebox.showinfo("Export", "Decoded data export functionality")
    
    def update_status_indicators(self):
        """Update various status indicators"""
        if self.is_streaming:
            self.connection_status.config(text="●", foreground='#27ae60')
            self.connection_indicator.config(text="🟢 Connected", foreground='#27ae60')
            
            # Update data received
            data_kb = self.bytes_received // 1024
            self.data_received_var.set(f"{data_kb:,} KB")
            
            # Update session time
            if self.session_start_time:
                elapsed = time.time() - self.session_start_time
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                self.session_time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
            # Update FSK state display
            if self.current_fsk_state:
                self.fsk_state_var.set(self.current_fsk_state)
            else:
                self.fsk_state_var.set("Analyzing...")
            
            # Update session statistics
            self.update_session_stats()
        else:
            self.connection_status.config(text="●", foreground='#95a5a6')
            self.connection_indicator.config(text="⚫ Disconnected", foreground='#95a5a6')
            self.fsk_state_var.set("Not streaming")
    
    def update_session_stats(self):
        """Update the session statistics display in the export tab"""
        if not hasattr(self, 'stats_text'):
            return
        
        try:
            # Calculate statistics
            current_time = time.time()
            session_duration = current_time - self.session_start_time if self.session_start_time else 0
            
            # Frequency statistics
            freq_count = len(self.frequency_buffer)
            avg_freq = sum(self.frequency_buffer) / freq_count if freq_count > 0 else 0
            min_freq = min(self.frequency_buffer) if freq_count > 0 else 0
            max_freq = max(self.frequency_buffer) if freq_count > 0 else 0
            
            # Binary statistics
            binary_count = len(self.binary_buffer)
            ones_count = sum(self.binary_buffer) if binary_count > 0 else 0
            zeros_count = binary_count - ones_count
            ones_ratio = ones_count / binary_count if binary_count > 0 else 0
            
            # Data rate
            data_rate = (self.bytes_received / 1024) / session_duration if session_duration > 0 else 0
            
            stats = f"""SESSION STATISTICS
{'=' * 40}

Connection Info:
  Duration: {session_duration:.0f} seconds ({session_duration/60:.1f} minutes)
  Data received: {self.bytes_received:,} bytes ({self.bytes_received/1024:.1f} KB)
  Average data rate: {data_rate:.2f} KB/s
  Chunks processed: {self.chunks_processed:,}

Frequency Analysis:
  Measurements: {freq_count:,}
  Average frequency: {avg_freq:.2f} Hz
  Frequency range: {min_freq:.2f} - {max_freq:.2f} Hz
  Current frequency: {self.frequency_buffer[-1] if freq_count > 0 else 0:.2f} Hz

Binary Decoding:
  Total bits decoded: {binary_count:,}
  Binary 1s: {ones_count:,} ({ones_ratio:.1%})
  Binary 0s: {zeros_count:,} ({1-ones_ratio:.1%})
  Bits per second: {binary_count/session_duration if session_duration > 0 else 0:.2f}

FSK State Analysis:
  Current state: {self.current_fsk_state or 'Unknown'}
  State changes: {len(self.fsk_state_history):,}
  FSK-1 (21.53Hz): {sum(1 for s in self.fsk_state_history if 'FSK-1' in s.get('state', ''))}/50 recent
  FSK-2 (26.92Hz): {sum(1 for s in self.fsk_state_history if 'FSK-2' in s.get('state', ''))}/50 recent  
  FSK-3 (32.30Hz): {sum(1 for s in self.fsk_state_history if 'FSK-3' in s.get('state', ''))}/50 recent

Data Quality:
  Waterfall snapshots: {len(self.waterfall_data):,}
  Log entries (binary): {len(self.binary_log):,}
  Log entries (frequency): {len(self.frequency_log):,}
  Log entries (waterfall): {len(self.waterfall_log):,}

Memory Usage:
  Frequency buffer: {len(self.frequency_buffer)}/1000 slots
  Binary buffer: {len(self.binary_buffer)}/500 slots
  Time buffer: {len(self.time_buffer)}/1000 slots
  Audio level buffer: {len(self.audio_level_buffer)}/1000 slots

Analysis:
  Data logging active: {'Yes' if self.log_binary_var.get() else 'No'}
  Frequency logging active: {'Yes' if self.log_frequency_var.get() else 'No'}
  Waterfall logging active: {'Yes' if self.log_waterfall_var.get() else 'No'}
"""
            
            self.stats_text.config(state='normal')
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, stats)
            self.stats_text.config(state='disabled')
            
        except Exception as e:
            print(f"Error updating session stats: {e}")
    
    def start_plot_updates(self):
        """Start plot updates using tkinter's after method instead of matplotlib animation"""
        self.update_plots(None)
        self.plot_update_timer = self.root.after(200, self.start_plot_updates)  # Update every 200ms
    
    def set_stream_url(self, url):
        """Set the stream URL and update status"""
        self.stream_url.set(url)
        if url.startswith("file://"):
            self.status_var.set(f"Ready to stream from local file")
        else:
            self.status_var.set(f"Ready to stream from: {url.split('//')[1].split(':')[0]}")
    
    def toggle_stream(self):
        """Start or stop the audio stream"""
        if not self.is_streaming:
            self.start_stream()
        else:
            self.stop_stream()
    
    def start_stream(self):
        """Start streaming audio from URL"""
        url = self.stream_url.get()
        
        if not url:
            messagebox.showwarning("No URL", "Please enter a stream URL")
            return
        
        self.is_streaming = True
        self.stream_btn.config(text="⏹️ Stop Stream")
        self.status_var.set("Connecting to stream...")
        
        # Initialize session
        self.session_start_time = time.time()
        session_time = time.strftime("%Y-%m-%d_%H-%M-%S")
        self.session_info_var.set(f"Session started: {session_time}")
        
        # Clear buffers and logs
        self.frequency_buffer.clear()
        self.binary_buffer.clear()
        self.time_buffer.clear()
        self.audio_level_buffer.clear()
        self.waterfall_data.clear()
        self.waterfall_times.clear()
        
        # Initialize logs
        self.binary_log = []
        self.frequency_log = []
        self.waterfall_log = []
        
        # Start streaming thread
        self.stream_thread = threading.Thread(target=self.stream_audio, args=(url,))
        self.stream_thread.daemon = True
        self.stream_thread.start()
        
        # Start analysis thread
        self.analysis_thread = threading.Thread(target=self.analyze_audio)
        self.analysis_thread.daemon = True
        self.analysis_thread.start()
    
    def stop_stream(self):
        """Stop the audio stream"""
        self.is_streaming = False
        self.stream_btn.config(text="🎵 Start Stream")
        self.status_var.set("Stream stopped")
    
    def stream_audio(self, url):
        """Stream audio from URL and put chunks in queue"""
        try:
            if url.startswith("file://"):
                # Local file streaming for testing
                self.stream_local_file(url[7:])
                return
            
            # HTTP stream
            print(f"Connecting to: {url}")
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            self.status_var.set("✅ Connected - Streaming live")
            print(f"Connected! Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            # Read audio chunks
            chunk_count = 0
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if not self.is_streaming:
                    break
                    
                if chunk:
                    self.audio_queue.put(chunk)
                    self.bytes_received += len(chunk)
                    chunk_count += 1
                    
                    if chunk_count % 100 == 0:  # Update status every 100 chunks
                        self.status_var.set(f"✅ Streaming: {self.bytes_received//1024}KB received")
                        print(f"Streamed {chunk_count} chunks, {self.bytes_received//1024}KB total")
                    
        except Exception as e:
            error_msg = f"❌ Stream error: {e}"
            self.status_var.set(error_msg)
            print(error_msg)
            self.is_streaming = False
            self.stream_btn.config(text="🎵 Start Stream")
    
    def stream_local_file(self, filepath):
        """Stream from local file for testing"""
        try:
            from scipy.io import wavfile
            sample_rate, audio_data = wavfile.read(filepath)
            
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            # Simulate streaming by sending chunks
            chunk_samples = self.chunk_size
            for i in range(0, len(audio_data), chunk_samples):
                if not self.is_streaming:
                    break
                
                chunk = audio_data[i:i + chunk_samples]
                # Convert to bytes (simplified)
                chunk_bytes = (chunk * 32767).astype(np.int16).tobytes()
                self.audio_queue.put(chunk_bytes)
                
                time.sleep(chunk_samples / sample_rate)  # Real-time simulation
                
        except Exception as e:
            self.status_var.set(f"❌ File error: {e}")
    
    def analyze_audio(self):
        """Continuously analyze audio chunks for frequency decoding"""
        audio_buffer = bytearray()
        
        while self.is_streaming:
            try:
                # Get audio chunk with timeout
                chunk = self.audio_queue.get(timeout=1.0)
                audio_buffer.extend(chunk)
                
                # Process when we have enough data
                if len(audio_buffer) >= self.chunk_size * 4:  # ~4 chunks for analysis
                    self.process_audio_chunk(audio_buffer)
                    # Keep some overlap
                    audio_buffer = audio_buffer[self.chunk_size * 2:]
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Analysis error: {e}")
    
    def process_audio_chunk(self, audio_bytes):
        """Process audio chunk and extract frequency"""
        try:
            self.chunks_processed += 1
            
            # Try multiple audio decoding methods
            audio_data = None
            
            # Method 1: Try as raw PCM (most common for web streams)
            try:
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                audio_data = audio_data / 32768.0  # Normalize
                if len(audio_data) < 100:  # Too short
                    audio_data = None
            except:
                pass
            
            # Method 2: Try as float32
            if audio_data is None:
                try:
                    audio_data = np.frombuffer(audio_bytes, dtype=np.float32)
                    if len(audio_data) < 100:
                        audio_data = None
                except:
                    pass
            
            # Method 3: Try with different byte order
            if audio_data is None:
                try:
                    audio_data = np.frombuffer(audio_bytes, dtype='>i2').astype(np.float32)  # Big-endian
                    audio_data = audio_data / 32768.0
                    if len(audio_data) < 100:
                        audio_data = None
                except:
                    pass
            
            if audio_data is None:
                print(f"Could not decode audio chunk of {len(audio_bytes)} bytes")
                return
            
            # Calculate audio level for diagnostics
            audio_level = np.mean(np.abs(audio_data))
            current_time = time.time()
            
            self.audio_level_buffer.append(audio_level)
            self.last_audio_time = current_time
            
            # Skip if audio is too quiet (likely silence or wrong format)
            if audio_level < 0.001:
                return
            
            print(f"Processing audio: {len(audio_data)} samples, level: {audio_level:.4f}")
            
            # Use larger window for better frequency resolution at low frequencies
            window_size = min(len(audio_data), 8192)  # Use more samples for better low-freq resolution
            if window_size < 2048:
                return
            
            # Take the first window_size samples
            audio_segment = audio_data[:window_size]
            windowed = audio_segment * signal.windows.hann(window_size)
            
            # FFT analysis
            fft_data = fft(windowed)
            freqs = fftfreq(window_size, 1/self.sample_rate)
            magnitude = np.abs(fft_data)
            
            # Store waterfall data (positive frequencies only)
            waterfall_freqs = freqs[:window_size//2]  # First half (positive frequencies)
            waterfall_magnitude = magnitude[:window_size//2]
            
            self.waterfall_data.append(waterfall_magnitude)
            self.waterfall_times.append(current_time)
            
            # Keep only recent waterfall data
            if len(self.waterfall_data) > self.max_waterfall_lines:
                self.waterfall_data.pop(0)
                self.waterfall_times.pop(0)
            
            # Debug: Show strongest frequencies (filter out interference)
            top_indices = np.argsort(magnitude)[-10:]  # Top 10 strongest frequencies
            for idx in top_indices:
                freq = freqs[idx]
                if freq > 0 and freq < 1000 and magnitude[idx] > 80:  # Only show strong signals
                    print(f"Strong frequency: {freq:.2f} Hz, magnitude: {magnitude[idx]:.2f}")
            
            # Focus on UVB-76 frequency range with improved detection
            target_range = (freqs >= 20.0) & (freqs <= 34.0)  # Narrower, more precise range
            if np.any(target_range):
                range_freqs = freqs[target_range]
                range_magnitude = magnitude[target_range]
                
                if len(range_magnitude) > 0:
                    # Find all significant peaks in UVB range
                    significant_peaks = []
                    for i, (freq, mag) in enumerate(zip(range_freqs, range_magnitude)):
                        if mag >= self.min_signal_strength:
                            significant_peaks.append((freq, mag, i))
                    
                    if significant_peaks:
                        # Sort by magnitude and take the strongest
                        significant_peaks.sort(key=lambda x: x[1], reverse=True)
                        peak_freq, peak_mag, peak_idx = significant_peaks[0]
                        
                        print(f"Peak in UVB range: {peak_freq:.2f} Hz, magnitude: {peak_mag:.2f}")
                        
                        # Check if this matches any known UVB-76 frequency
                        is_uvb_frequency = False
                        for tone_name, tone_freq in self.uvb76_frequencies.items():
                            if abs(peak_freq - tone_freq) <= self.freq_tolerance * 2:  # Slightly wider tolerance for detection
                                is_uvb_frequency = True
                                break
                        
                        # Only process if it's a known UVB frequency and strong enough
                        if is_uvb_frequency and peak_mag >= self.min_signal_strength:
                            print(f"Adding frequency: {peak_freq:.2f} Hz")
                            
                            # Update FSK state tracking
                            self.update_fsk_state(peak_freq, peak_mag)
                            
                            # Add to buffers
                            self.frequency_buffer.append(peak_freq)
                            self.time_buffer.append(current_time)
                            
                            # Log frequency data if enabled
                            if self.log_frequency_var.get():
                                self.frequency_log.append({
                                    'timestamp': current_time,
                                    'session_time': current_time - self.session_start_time if self.session_start_time else 0,
                                    'frequency': peak_freq,
                                    'magnitude': peak_mag,
                                    'audio_level': audio_level
                                })
                            
                            # Decode frequency to binary state using real FSK tones
                            binary_state = self.frequency_to_binary_debug(peak_freq)
                            if binary_state is not None:
                                self.binary_buffer.append(binary_state)
                                
                                # Log binary data if enabled
                                if self.log_binary_var.get():
                                    self.binary_log.append({
                                        'timestamp': current_time,
                                        'session_time': current_time - self.session_start_time if self.session_start_time else 0,
                                        'binary_state': binary_state,
                                        'frequency': peak_freq,
                                        'bit_number': len(self.binary_log) + 1
                                    })
                                
                                self.update_binary_display()
            
            # Store waterfall data for logging if enabled
            if self.log_waterfall_var.get() and len(self.waterfall_data) > 0:
                self.waterfall_log.append({
                    'timestamp': current_time,
                    'session_time': current_time - self.session_start_time if self.session_start_time else 0,
                    'frequencies': waterfall_freqs.tolist(),
                    'magnitudes': waterfall_magnitude.tolist()
                })
        
        except Exception as e:
            print(f"Processing error: {e}")
            import traceback
            traceback.print_exc()
    
    def frequency_to_binary_debug(self, frequency):
        """Convert frequency to FSK state using traditional 2-tone FSK"""
        
        # Match against actual UVB-76 FSK data tones with tolerance
        freq_1 = self.uvb76_frequencies['freq_1']  # 21.53 Hz
        freq_2 = self.uvb76_frequencies['freq_2']  # 26.92 Hz  
        freq_3 = self.uvb76_frequencies['freq_3']  # 32.30 Hz
        tol = self.freq_tolerance
        
        if abs(frequency - freq_1) <= tol:
            print(f"FSK Data Tone 1: {frequency:.2f} Hz (Binary 0)")
            return 0
        elif abs(frequency - freq_2) <= tol:
            print(f"FSK Data Tone 2: {frequency:.2f} Hz (Binary 1)")  
            return 1
        elif abs(frequency - freq_3) <= tol:
            print(f"FSK Carrier/Buzzer: {frequency:.2f} Hz (Ignored)")
            return None  # Ignore carrier - only decode actual data tones
        else:
            # Check if it's close to UVB-76 range but doesn't match known tones
            if 20.0 <= frequency <= 35.0:
                print(f"Unknown UVB tone: {frequency:.2f} Hz (Ignored)")
                return None  # Ignore unknown tones
            else:
                # Outside UVB-76 range - likely interference
                return None
    
    def frequency_to_binary(self, frequency):
        """Convert frequency to FSK state using traditional 2-tone FSK"""
        
        # Match against actual UVB-76 FSK data tones with tolerance  
        freq_1 = self.uvb76_frequencies['freq_1']  # 21.53 Hz
        freq_2 = self.uvb76_frequencies['freq_2']  # 26.92 Hz  
        freq_3 = self.uvb76_frequencies['freq_3']  # 32.30 Hz
        tol = self.freq_tolerance
        
        if abs(frequency - freq_1) <= tol:
            return 0  # Binary 0
        elif abs(frequency - freq_2) <= tol:
            return 1  # Binary 1
        elif abs(frequency - freq_3) <= tol:
            return None  # Ignore carrier/buzzer - only decode data tones
        else:
            # Ignore unknown or out-of-range frequencies
            return None
    
    def update_fsk_state(self, frequency, magnitude):
        """Track FSK state changes and update status"""
        current_time = time.time()
        
        # Determine FSK state
        freq_1 = self.uvb76_frequencies['freq_1']  # 21.53 Hz
        freq_2 = self.uvb76_frequencies['freq_2']  # 26.92 Hz  
        freq_3 = self.uvb76_frequencies['freq_3']  # 32.30 Hz
        tol = self.freq_tolerance
        
        new_state = None
        if abs(frequency - freq_1) <= tol:
            new_state = f"FSK-1 ({freq_1:.2f}Hz)"
        elif abs(frequency - freq_2) <= tol:
            new_state = f"FSK-2 ({freq_2:.2f}Hz)"
        elif abs(frequency - freq_3) <= tol:
            new_state = f"FSK-3 ({freq_3:.2f}Hz)"
        else:
            new_state = f"Unknown ({frequency:.2f}Hz)"
        
        # Update state if changed
        if new_state != self.current_fsk_state:
            self.last_fsk_change = current_time
            self.fsk_state_history.append({
                'state': new_state,
                'frequency': frequency,
                'magnitude': magnitude,
                'timestamp': current_time,
                'duration': current_time - (self.last_fsk_change or current_time)
            })
            self.current_fsk_state = new_state
            print(f"FSK state change: {new_state} (mag: {magnitude:.1f})")
        
        return new_state
    
    def update_binary_display(self):
        """Update the binary stream display with decoding"""
        if len(self.binary_buffer) < 1:  # Show data immediately when any bit is available
            return
        
        # Get recent binary data
        recent_bits = list(self.binary_buffer)[-200:]  # Last 200 bits
        
        # Create readable display for traditional 2-state FSK system
        # 0 = 21.53Hz (data tone), 1 = 26.92Hz (data tone)
        # 32.30Hz carrier/buzzer periods are ignored (not included in binary_buffer)
        binary_string = ''.join([str(bit) for bit in recent_bits])
        
        # Group into bytes for readability 
        grouped = ' '.join([binary_string[i:i+8] for i in range(0, len(binary_string), 8)])
        
        # Show frequency distribution  
        freq_counts = {0: 0, 1: 0}
        for bit in recent_bits:
            freq_counts[bit] = freq_counts.get(bit, 0) + 1
        
        freq_summary = f"Data Tone Distribution: 0={freq_counts[0]} (21.53Hz), 1={freq_counts[1]} (26.92Hz)"
        
        # Decode binary data (all bits are now 0s and 1s)
        decode_preview = ""
        
        if len(recent_bits) >= 8:
            try:
                # Quick ASCII attempt
                ascii_chars = ""
                for i in range(0, len(binary_string) - 7, 8):
                    byte = binary_string[i:i+8]
                    if len(byte) == 8:
                        val = int(byte, 2)
                        if 32 <= val <= 126:
                            ascii_chars += chr(val)
                        else:
                            ascii_chars += f"[{val}]"
                
                if ascii_chars and len(ascii_chars.strip('[]0123456789')) > 2:
                    decode_preview = f"ASCII: {ascii_chars[:30]}"
                else:
                    # Try decimal interpretation
                    decimal_vals = []
                    for i in range(0, min(40, len(binary_string) - 7), 8):
                        byte = binary_string[i:i+8]
                        if len(byte) == 8:
                            decimal_vals.append(str(int(byte, 2)))
                    
                    if decimal_vals:
                        decode_preview = f"Decimal: {' '.join(decimal_vals[:10])}"
            
            except Exception as e:
                decode_preview = f"Decode error: {e}"
        
        # Update display
        self.binary_text.config(state='normal')
        self.binary_text.delete(1.0, tk.END)
        self.binary_text.insert(1.0, f"Binary Data: {grouped}\n")
        self.binary_text.insert(tk.END, f"Legend: 0=21.53Hz (Data), 1=26.92Hz (Data), 32.30Hz=Carrier (Ignored)\n")
        self.binary_text.insert(tk.END, f"Total data bits: {len(self.binary_buffer)} (carrier periods excluded)\n")
        self.binary_text.insert(tk.END, f"{freq_summary}\n")
        if decode_preview:
            self.binary_text.insert(tk.END, f"{decode_preview}\n")
        
        # Look for patterns in full sequence
        patterns_result = self.analyze_patterns(list(self.binary_buffer))
        if isinstance(patterns_result, dict):
            patterns = patterns_result.get('patterns', [])
        else:
            patterns = patterns_result
        
        self.binary_text.insert(tk.END, f"Patterns: {patterns}")
        
        # Auto-scroll if enabled
        if hasattr(self, 'auto_scroll_var') and self.auto_scroll_var.get():
            self.binary_text.see(tk.END)
        
        self.binary_text.config(state='disabled')
        
        # Update pattern analysis
        self.update_pattern_analysis(recent_bits)
    
    def analyze_patterns(self, bits):
        """Analyze binary sequence for patterns and decode to text/numbers"""
        if len(bits) < 8:
            return "Insufficient data"
        
        patterns = []
        bit_string = ''.join(map(str, bits))
        
        # Look for repeating sequences
        for length in [4, 8, 16]:
            for i in range(len(bit_string) - length):
                pattern = bit_string[i:i+length]
                count = bit_string.count(pattern)
                if count > 2 and len(pattern) >= 4:
                    patterns.append(f"{pattern}({count}x)")
        
        # Try to decode as various formats
        decoded_results = self.decode_binary_sequence(bits)
        
        return {
            'patterns': patterns[:5] if patterns else ["No clear patterns"],
            'decoded': decoded_results
        }
    
    def decode_binary_sequence(self, bits):
        """Attempt to decode binary sequence using multiple methods"""
        if len(bits) < 8:
            return {"error": "Need at least 8 bits for decoding"}
        
        bit_string = ''.join(map(str, bits))
        results = {}
        
        # Method 1: ASCII decoding (8-bit bytes)
        try:
            ascii_result = ""
            for i in range(0, len(bit_string) - 7, 8):
                byte = bit_string[i:i+8]
                if len(byte) == 8:
                    decimal_value = int(byte, 2)
                    if 32 <= decimal_value <= 126:  # Printable ASCII
                        ascii_result += chr(decimal_value)
                    else:
                        ascii_result += f"[{decimal_value}]"
            
            if ascii_result:
                results['ascii_8bit'] = ascii_result[:50]  # First 50 characters
        except:
            results['ascii_8bit'] = "Decode failed"
        
        # Method 2: Numbers as 4-bit nibbles (0-15)
        try:
            nibbles = []
            for i in range(0, len(bit_string) - 3, 4):
                nibble = bit_string[i:i+4]
                if len(nibble) == 4:
                    nibbles.append(str(int(nibble, 2)))
            
            if nibbles:
                results['nibbles_4bit'] = ' '.join(nibbles[:20])  # First 20 nibbles
        except:
            results['nibbles_4bit'] = "Decode failed"
        
        # Method 3: Numbers as 8-bit bytes (0-255)
        try:
            bytes_decimal = []
            for i in range(0, len(bit_string) - 7, 8):
                byte = bit_string[i:i+8]
                if len(byte) == 8:
                    bytes_decimal.append(str(int(byte, 2)))
            
            if bytes_decimal:
                results['bytes_decimal'] = ' '.join(bytes_decimal[:15])  # First 15 bytes
        except:
            results['bytes_decimal'] = "Decode failed"
        
        # Method 4: Hexadecimal representation
        try:
            hex_result = ""
            for i in range(0, len(bit_string) - 7, 8):
                byte = bit_string[i:i+8]
                if len(byte) == 8:
                    hex_result += f"{int(byte, 2):02X} "
            
            if hex_result:
                results['hex_bytes'] = hex_result[:60]  # First 60 chars
        except:
            results['hex_bytes'] = "Decode failed"
        
        # Method 5: Look for Baudot code (5-bit)
        try:
            baudot_letters = {
                '11000': 'A', '10011': 'B', '01110': 'C', '10010': 'D', '10000': 'E',
                '10110': 'F', '01011': 'G', '00101': 'H', '01100': 'I', '11010': 'J',
                '11110': 'K', '01001': 'L', '00111': 'M', '00110': 'N', '00011': 'O',
                '01101': 'P', '11101': 'Q', '01010': 'R', '10100': 'S', '00001': 'T',
                '11100': 'U', '01111': 'V', '11001': 'W', '10111': 'X', '10101': 'Y',
                '10001': 'Z'
            }
            
            baudot_result = ""
            for i in range(0, len(bit_string) - 4, 5):
                code = bit_string[i:i+5]
                if len(code) == 5:
                    if code in baudot_letters:
                        baudot_result += baudot_letters[code]
                    else:
                        baudot_result += "?"
            
            if baudot_result:
                results['baudot_5bit'] = baudot_result[:30]  # First 30 characters
        except:
            results['baudot_5bit'] = "Decode failed"
        
        # Method 6: BCD (Binary Coded Decimal)
        try:
            bcd_result = ""
            for i in range(0, len(bit_string) - 3, 4):
                nibble = bit_string[i:i+4]
                if len(nibble) == 4:
                    value = int(nibble, 2)
                    if 0 <= value <= 9:
                        bcd_result += str(value)
                    else:
                        bcd_result += "X"  # Invalid BCD
            
            if bcd_result:
                results['bcd_decimal'] = bcd_result[:40]  # First 40 digits
        except:
            results['bcd_decimal'] = "Decode failed"
        
        # Method 7: Custom UVB-76 potential encodings
        try:
            # Check for common sync patterns
            sync_patterns = {
                '10101010': 'SYNC_AA',
                '01010101': 'SYNC_55', 
                '11110000': 'SYNC_F0',
                '00001111': 'SYNC_0F',
                '11111111': 'ALL_ONES',
                '00000000': 'ALL_ZEROS'
            }
            
            found_syncs = []
            for pattern, name in sync_patterns.items():
                count = bit_string.count(pattern)
                if count > 0:
                    found_syncs.append(f"{name}({count})")
            
            results['sync_patterns'] = ', '.join(found_syncs) if found_syncs else "None detected"
            
        except:
            results['sync_patterns'] = "Analysis failed"
        
        # Method 8: Statistical analysis
        try:
            ones_count = bit_string.count('1')
            zeros_count = bit_string.count('0')
            total_bits = len(bit_string)
            
            # Calculate entropy (simple version)
            if total_bits > 0:
                p1 = ones_count / total_bits
                p0 = zeros_count / total_bits
                entropy = 0
                if p1 > 0:
                    entropy -= p1 * np.log2(p1)
                if p0 > 0:
                    entropy -= p0 * np.log2(p0)
                
                results['statistics'] = f"1s:{ones_count}({p1:.1%}) 0s:{zeros_count}({p0:.1%}) Entropy:{entropy:.2f}"
        except:
            results['statistics'] = "Calc failed"
        
        return results
    
    def detect_monolit_coding(self, bits):
        """Detect Monolit coding patterns in binary sequence"""
        if len(bits) < 64:  # Need sufficient data
            return {"error": "Insufficient data for Monolit analysis"}
        
        bit_string = ''.join(map(str, bits))
        results = {}
        
        try:
            # Method 1: Look for repeated callsigns (typical in Monolit)
            # Callsigns are usually 3-4 characters, transmitted twice
            callsign_patterns = []
            
            # Convert to ASCII and look for repeated patterns
            ascii_chars = ""
            for i in range(0, len(bit_string) - 7, 8):
                byte = bit_string[i:i+8]
                if len(byte) == 8:
                    val = int(byte, 2)
                    if 32 <= val <= 126:  # Printable ASCII
                        ascii_chars += chr(val)
                    else:
                        ascii_chars += "."
            
            # Look for repeated 3-4 character sequences (callsigns read twice)
            for length in [3, 4, 5]:
                for i in range(len(ascii_chars) - length * 2):
                    pattern = ascii_chars[i:i+length]
                    next_pattern = ascii_chars[i+length:i+length*2]
                    if pattern == next_pattern and pattern.isalnum():
                        callsign_patterns.append(f"'{pattern}' (repeated)")
            
            results['callsign_candidates'] = callsign_patterns[:5] if callsign_patterns else "None detected"
            
            # Method 2: Look for five-digit ID groups
            # Convert to decimal and look for 5-digit patterns
            decimal_sequence = ""
            for i in range(0, len(bit_string) - 7, 8):
                byte = bit_string[i:i+8]
                if len(byte) == 8:
                    val = int(byte, 2)
                    if 48 <= val <= 57:  # ASCII digits 0-9
                        decimal_sequence += chr(val)
                    else:
                        decimal_sequence += " "
            
            # Look for 5-digit groups separated by spaces/delimiters
            import re
            five_digit_groups = re.findall(r'\b\d{5}\b', decimal_sequence)
            results['five_digit_groups'] = five_digit_groups[:10] if five_digit_groups else "None detected"
            
            # Method 3: Look for eight-digit message blocks
            eight_digit_groups = re.findall(r'\b\d{8}\b', decimal_sequence)
            results['eight_digit_blocks'] = eight_digit_groups[:5] if eight_digit_groups else "None detected"
            
            # Method 4: Look for code words (typically 4-6 letters)
            code_word_candidates = re.findall(r'\b[A-Z]{4,6}\b', ascii_chars.upper())
            results['code_word_candidates'] = code_word_candidates[:5] if code_word_candidates else "None detected"
            
            # Method 5: Analyze transmission structure
            # Look for typical Monolit timing patterns
            structure_analysis = []
            
            if callsign_patterns:
                structure_analysis.append("✓ Repeated callsign pattern detected")
            if five_digit_groups:
                structure_analysis.append(f"✓ {len(five_digit_groups)} five-digit ID groups found")
            if eight_digit_groups:
                structure_analysis.append(f"✓ {len(eight_digit_groups)} eight-digit message blocks found")
            if code_word_candidates:
                structure_analysis.append(f"✓ {len(code_word_candidates)} code word candidates found")
            
            # Calculate Monolit likelihood score
            score = 0
            if callsign_patterns: score += 30
            if five_digit_groups: score += 25
            if eight_digit_groups: score += 25
            if code_word_candidates: score += 20
            
            if score >= 70:
                likelihood = "HIGH - Strong Monolit characteristics"
            elif score >= 40:
                likelihood = "MEDIUM - Some Monolit patterns"
            elif score >= 20:
                likelihood = "LOW - Few Monolit indicators"
            else:
                likelihood = "NONE - No clear Monolit patterns"
            
            results['monolit_likelihood'] = likelihood
            results['structure_analysis'] = structure_analysis if structure_analysis else ["No clear Monolit structure detected"]
            
            # Method 6: Look for timing patterns (if we have timing data)
            if hasattr(self, 'binary_log') and len(self.binary_log) > 10:
                # Analyze timing between binary state changes
                timing_intervals = []
                for i in range(1, min(len(self.binary_log), 50)):
                    interval = self.binary_log[i]['session_time'] - self.binary_log[i-1]['session_time']
                    if 0.1 < interval < 10:  # Reasonable timing range
                        timing_intervals.append(interval)
                
                if timing_intervals:
                    avg_interval = sum(timing_intervals) / len(timing_intervals)
                    results['timing_analysis'] = f"Avg bit interval: {avg_interval:.2f}s (typical Monolit: 0.5-2.0s)"
                else:
                    results['timing_analysis'] = "Insufficient timing data"
            
        except Exception as e:
            results['error'] = f"Monolit analysis failed: {e}"
        
        return results
    
    def update_pattern_analysis(self, bits):
        """Update detailed pattern analysis with decoding"""
        if len(bits) < 16:
            return
        
        analysis_result = self.analyze_patterns(bits)
        patterns = analysis_result.get('patterns', [])
        decoded = analysis_result.get('decoded', {})
        
        # Get Monolit analysis
        monolit_result = self.detect_monolit_coding(bits)
        
        analysis = "PATTERN ANALYSIS & DECODING:\n"
        analysis += "=" * 50 + "\n\n"
        
        # Basic statistics
        ones_ratio = sum(bits) / len(bits)
        analysis += f"Bit statistics:\n"
        analysis += f"  1s ratio: {ones_ratio:.2%}\n"
        analysis += f"  0s ratio: {1-ones_ratio:.2%}\n"
        analysis += f"  Total bits: {len(bits)}\n\n"
        
        # Repeating patterns
        analysis += f"Repeating patterns:\n"
        for pattern in patterns:
            analysis += f"  {pattern}\n"
        analysis += "\n"
        
        # Decoding attempts
        analysis += "DECODING ATTEMPTS:\n"
        analysis += "-" * 20 + "\n"
        
        if 'ascii_8bit' in decoded:
            analysis += f"ASCII (8-bit): {decoded['ascii_8bit']}\n"
        
        if 'baudot_5bit' in decoded:
            analysis += f"Baudot (5-bit): {decoded['baudot_5bit']}\n"
        
        if 'bytes_decimal' in decoded:
            analysis += f"Decimal bytes: {decoded['bytes_decimal']}\n"
        
        if 'hex_bytes' in decoded:
            analysis += f"Hex bytes: {decoded['hex_bytes']}\n"
        
        if 'nibbles_4bit' in decoded:
            analysis += f"4-bit nibbles: {decoded['nibbles_4bit']}\n"
        
        if 'bcd_decimal' in decoded:
            analysis += f"BCD decimal: {decoded['bcd_decimal']}\n"
        
        if 'sync_patterns' in decoded:
            analysis += f"Sync patterns: {decoded['sync_patterns']}\n"
        
        if 'statistics' in decoded:
            analysis += f"Statistics: {decoded['statistics']}\n"
        
        # Monolit coding analysis
        analysis += f"\nMONOLIT CODING ANALYSIS:\n"
        analysis += "-" * 25 + "\n"
        
        if 'error' not in monolit_result:
            analysis += f"Likelihood: {monolit_result.get('monolit_likelihood', 'Unknown')}\n\n"
            
            analysis += f"Callsign Candidates: {monolit_result.get('callsign_candidates', 'None')}\n"
            analysis += f"5-Digit ID Groups: {monolit_result.get('five_digit_groups', 'None')}\n"
            analysis += f"8-Digit Message Blocks: {monolit_result.get('eight_digit_blocks', 'None')}\n"
            analysis += f"Code Word Candidates: {monolit_result.get('code_word_candidates', 'None')}\n"
            
            if 'timing_analysis' in monolit_result:
                analysis += f"Timing: {monolit_result['timing_analysis']}\n"
            
            analysis += f"\nStructure Analysis:\n"
            structure = monolit_result.get('structure_analysis', [])
            for item in structure:
                analysis += f"  {item}\n"
        else:
            analysis += f"Error: {monolit_result['error']}\n"
        
        # Run length encoding
        analysis += f"\nRUN LENGTHS:\n"
        analysis += "-" * 12 + "\n"
        runs = []
        current_bit = bits[0]
        current_run = 1
        
        for bit in bits[1:]:
            if bit == current_bit:
                current_run += 1
            else:
                runs.append((current_bit, current_run))
                current_bit = bit
                current_run = 1
        runs.append((current_bit, current_run))
        
        for bit, length in runs[-10:]:  # Show last 10 runs
            analysis += f"  {bit}: {length} bits\n"
        
        # Look for potential message boundaries
        analysis += f"\nPOSSIBLE MESSAGE STRUCTURE:\n"
        analysis += "-" * 25 + "\n"
        bit_string = ''.join(map(str, bits))
        
        # Common message delimiters
        delimiters = {
            '1010': 'Alt pattern',
            '0101': 'Alt pattern',
            '1111': 'Sync/start',
            '0000': 'Null/end',
            '11110000': 'Byte sync',
            '10101010': 'Clock sync'
        }
        
        for delimiter, description in delimiters.items():
            positions = []
            start = 0
            while True:
                pos = bit_string.find(delimiter, start)
                if pos == -1:
                    break
                positions.append(pos)
                start = pos + 1
            
            if positions:
                analysis += f"  {delimiter} ({description}): positions {positions[-5:]}\n"
        
        # Suggest most likely interpretation
        analysis += f"\nMOST LIKELY INTERPRETATION:\n"
        analysis += "-" * 26 + "\n"
        
        # Analyze bit distribution and patterns
        if ones_ratio < 0.3:
            analysis += "  • Low 1s ratio suggests structured data\n"
        elif ones_ratio > 0.7:
            analysis += "  • High 1s ratio suggests sync/fill pattern\n"
        else:
            analysis += "  • Balanced bit ratio suggests data content\n"
        
        # Check for common patterns
        if '10101010' in bit_string or '01010101' in bit_string:
            analysis += "  • Contains alternating patterns (likely sync)\n"
        
        if len(set(runs)) < 5:  # Few different run lengths
            analysis += "  • Limited run lengths suggest digital encoding\n"
        
        # ASCII likelihood
        try:
            ascii_chars = 0
            for i in range(0, len(bit_string) - 7, 8):
                byte = bit_string[i:i+8]
                if len(byte) == 8:
                    val = int(byte, 2)
                    if 32 <= val <= 126:
                        ascii_chars += 1
            
            if ascii_chars > len(bit_string) // 16:  # >50% valid ASCII
                analysis += "  • High ASCII validity - possible text data\n"
        except:
            pass
        
        self.pattern_text.config(state='normal')
        self.pattern_text.delete(1.0, tk.END)
        self.pattern_text.insert(1.0, analysis)
        
        # Auto-scroll if enabled
        if hasattr(self, 'auto_scroll_var') and self.auto_scroll_var.get():
            self.pattern_text.see(tk.END)
        
        self.pattern_text.config(state='disabled')
    
    def update_plots(self, frame):
        """Update real-time plots for the modern 2x2 layout"""
        try:
            # Update status indicators first
            self.update_status_indicators()
            
            # Update binary display if we have data
            if len(self.binary_buffer) > 0:
                self.update_binary_display()
            
            # Convert absolute times to relative times
            if self.time_buffer and len(self.time_buffer) > 0:
                base_time = self.time_buffer[0]
                times = [(t - base_time) for t in self.time_buffer]
            else:
                times = []
            
            # Update frequency plot - ensure arrays match
            if len(times) >= 2 and len(self.frequency_buffer) >= 2 and len(times) == len(self.frequency_buffer):
                self.line_freq.set_data(times, list(self.frequency_buffer))
                
                # Adjust x-axis to show last 60 seconds
                if times:
                    self.axes[0, 0].set_xlim(max(0, times[-1] - 60), times[-1] + 5)
                
                # Update frequency state indicator using actual UVB-76 frequencies
                if self.frequency_buffer:
                    current_freq = self.frequency_buffer[-1]
                    # Use the same logic as frequency_to_binary with tolerance
                    freq_1 = self.uvb76_frequencies['freq_1']  # 21.53 Hz
                    freq_2 = self.uvb76_frequencies['freq_2']  # 26.92 Hz  
                    freq_3 = self.uvb76_frequencies['freq_3']  # 32.30 Hz
                    tol = self.freq_tolerance * 2  # Wider tolerance for display
                    
                    if abs(current_freq - freq_1) <= tol:
                        self.freq_state_var.set(f"{current_freq:.1f} Hz (FSK-1: Binary 0)")
                    elif abs(current_freq - freq_2) <= tol:
                        self.freq_state_var.set(f"{current_freq:.1f} Hz (FSK-2: Binary 1)")
                    elif abs(current_freq - freq_3) <= tol:
                        self.freq_state_var.set(f"{current_freq:.1f} Hz (FSK-3: Carrier/Buzzer)")
                    elif 20.0 <= current_freq <= 35.0:
                        self.freq_state_var.set(f"{current_freq:.1f} Hz (Unknown UVB tone)")
                    else:
                        self.freq_state_var.set(f"{current_freq:.1f} Hz (Non-UVB)")
            
            # Update binary state plot - ensure arrays match
            if len(self.binary_buffer) >= 2:
                # Create matching time array for binary data
                binary_count = len(self.binary_buffer)
                if len(times) >= binary_count:
                    binary_times = times[-binary_count:]  # Take last N times to match binary data
                    
                    if len(binary_times) == len(self.binary_buffer):
                        self.line_binary.set_data(binary_times, list(self.binary_buffer))
                        if binary_times:
                            self.axes[0, 1].set_xlim(max(0, binary_times[-1] - 60), binary_times[-1] + 5)
                            self.axes[0, 1].set_ylim(-0.2, 1.2)  # Set proper limits for binary 0,1
            
            # Update waterfall plot
            if len(self.waterfall_data) > 5:
                self.axes[1, 0].clear()
                
                # Create waterfall display
                waterfall_array = np.array(self.waterfall_data)
                
                # Focus on 0-100 Hz range for visualization
                freq_range_indices = slice(0, min(200, waterfall_array.shape[1]))  # ~100 Hz at 44.1kHz sampling
                
                # Display as image (time vs frequency)
                im = self.axes[1, 0].imshow(waterfall_array[:, freq_range_indices], 
                                          aspect='auto', origin='lower', 
                                          cmap='viridis', interpolation='bilinear')
                
                self.axes[1, 0].set_title('Real-time Waterfall (0-100 Hz)')
                self.axes[1, 0].set_xlabel('Frequency Bin')
                self.axes[1, 0].set_ylabel('Time (recent)')
            
            # Update frequency histogram
            if len(self.frequency_buffer) > 10:
                self.axes[1, 1].clear()
                self.axes[1, 1].hist(list(self.frequency_buffer), bins=30, alpha=0.7, 
                                    color='#3498db', edgecolor='white', linewidth=0.5)
                self.axes[1, 1].set_title('Frequency Distribution')
                self.axes[1, 1].set_xlabel('Frequency (Hz)')
                self.axes[1, 1].set_ylabel('Count')
                self.axes[1, 1].set_xlim(18, 35)
                self.axes[1, 1].grid(True, alpha=0.3)
                
                # Add state region indicators with modern colors using actual UVB-76 frequencies
                freq_1 = self.uvb76_frequencies['freq_1']  # 21.53 Hz
                freq_2 = self.uvb76_frequencies['freq_2']  # 26.92 Hz  
                freq_3 = self.uvb76_frequencies['freq_3']  # 32.30 Hz
                tol = self.freq_tolerance * 2  # Wider tolerance for visualization
                
                self.axes[1, 1].axvspan(freq_1-tol, freq_1+tol, alpha=0.3, color='#e74c3c', label=f'Data Tone 0 ({freq_1}Hz)')
                self.axes[1, 1].axvspan(freq_2-tol, freq_2+tol, alpha=0.3, color='#27ae60', label=f'Data Tone 1 ({freq_2}Hz)') 
                self.axes[1, 1].axvspan(freq_3-tol, freq_3+tol, alpha=0.2, color='#95a5a6', label=f'Carrier/Buzzer ({freq_3}Hz)')
                
                # Show wider UVB-76 range
                self.axes[1, 1].axvspan(19, 21, alpha=0.1, color='#bdc3c7')
                self.axes[1, 1].axvspan(35, 37, alpha=0.1, color='#bdc3c7')
                self.axes[1, 1].legend(loc='upper right')
            
            # Update data rate calculation
            if hasattr(self, 'last_bytes_received'):
                time_diff = time.time() - getattr(self, 'last_rate_update', time.time())
                if time_diff >= 1.0:  # Update every second
                    bytes_diff = self.bytes_received - getattr(self, 'last_bytes_received', 0)
                    rate_kbps = (bytes_diff / 1024) / time_diff
                    self.data_rate_var.set(f"{rate_kbps:.1f} KB/s")
                    self.last_bytes_received = self.bytes_received
                    self.last_rate_update = time.time()
            else:
                self.last_bytes_received = self.bytes_received
                self.last_rate_update = time.time()
            
            # Redraw the canvas
            self.canvas.draw_idle()
            
        except Exception as e:
            print(f"Plot update error: {e}")  # Non-fatal error handling
    
    def save_figure_png(self):
        """Save current figure as PNG"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            title="Save Figure as PNG",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                self.fig.savefig(filename, dpi=300, bbox_inches='tight', format='png')
                messagebox.showinfo("Success", f"Figure saved as:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save figure:\n{e}")
    
    def save_figure_pdf(self):
        """Save current figure as PDF"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            title="Save Figure as PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                self.fig.savefig(filename, dpi=300, bbox_inches='tight', format='pdf')
                messagebox.showinfo("Success", f"Figure saved as:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save figure:\n{e}")
    
    def save_figure_svg(self):
        """Save current figure as SVG"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            title="Save Figure as SVG",
            defaultextension=".svg",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                self.fig.savefig(filename, bbox_inches='tight', format='svg')
                messagebox.showinfo("Success", f"Figure saved as:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save figure:\n{e}")
    
    def export_binary_log(self):
        """Export complete binary log to CSV"""
        if not self.binary_log:
            messagebox.showwarning("No Data", "No binary data to export.")
            return
        
        from tkinter import filedialog
        import pandas as pd
        
        filename = filedialog.asksaveasfilename(
            title="Export Binary Log",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                df = pd.DataFrame(self.binary_log)
                df.to_csv(filename, index=False)
                
                # Also save a binary-only text file
                binary_filename = filename.replace('.csv', '_binary.txt')
                binary_sequence = ''.join([str(entry['binary_state']) for entry in self.binary_log])
                
                with open(binary_filename, 'w') as f:
                    f.write(f"UVB-76 Binary Sequence\n")
                    f.write(f"Session: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.session_start_time))}\n")
                    f.write(f"Total bits: {len(binary_sequence)}\n")
                    f.write(f"Duration: {self.binary_log[-1]['session_time']:.1f} seconds\n\n")
                    
                    # Write binary in groups of 8
                    for i in range(0, len(binary_sequence), 64):
                        line = binary_sequence[i:i+64]
                        formatted_line = ' '.join([line[j:j+8] for j in range(0, len(line), 8)])
                        f.write(f"{i//8:04d}: {formatted_line}\n")
                
                messagebox.showinfo("Success", f"Binary log exported to:\n{filename}\n{binary_filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export binary log:\n{e}")
    
    def export_frequency_log(self):
        """Export complete frequency log to CSV"""
        if not self.frequency_log:
            messagebox.showwarning("No Data", "No frequency data to export.")
            return
        
        from tkinter import filedialog
        import pandas as pd
        
        filename = filedialog.asksaveasfilename(
            title="Export Frequency Log",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                df = pd.DataFrame(self.frequency_log)
                df.to_csv(filename, index=False)
                messagebox.showinfo("Success", f"Frequency log exported to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export frequency log:\n{e}")
    
    def export_all_data(self):
        """Export all logged data to multiple files"""
        if not (self.binary_log or self.frequency_log or self.waterfall_log):
            messagebox.showwarning("No Data", "No data to export.")
            return
        
        from tkinter import filedialog
        import pandas as pd
        import json
        
        # Get base filename
        filename = filedialog.asksaveasfilename(
            title="Export All Data (base filename)",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        base_name = filename.replace('.csv', '')
        session_time = time.strftime("%Y%m%d_%H%M%S", time.localtime(self.session_start_time))
        
        try:
            exported_files = []
            
            # Export binary data
            if self.binary_log:
                binary_file = f"{base_name}_binary_{session_time}.csv"
                df_binary = pd.DataFrame(self.binary_log)
                df_binary.to_csv(binary_file, index=False)
                exported_files.append(binary_file)
            
            # Export frequency data
            if self.frequency_log:
                freq_file = f"{base_name}_frequency_{session_time}.csv"
                df_freq = pd.DataFrame(self.frequency_log)
                df_freq.to_csv(freq_file, index=False)
                exported_files.append(freq_file)
            
            # Export waterfall data (as JSON due to nested arrays)
            if self.waterfall_log:
                waterfall_file = f"{base_name}_waterfall_{session_time}.json"
                with open(waterfall_file, 'w') as f:
                    json.dump(self.waterfall_log, f, indent=2)
                exported_files.append(waterfall_file)
            
            # Create session summary
            summary_file = f"{base_name}_summary_{session_time}.txt"
            with open(summary_file, 'w') as f:
                f.write(f"UVB-76 Analysis Session Summary\n")
                f.write(f"=" * 40 + "\n\n")
                f.write(f"Session Start: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.session_start_time))}\n")
                f.write(f"Duration: {time.time() - self.session_start_time:.1f} seconds\n")
                f.write(f"Stream URL: {self.stream_url.get()}\n\n")
                
                f.write(f"Data Collected:\n")
                f.write(f"- Binary bits: {len(self.binary_log)}\n")
                f.write(f"- Frequency measurements: {len(self.frequency_log)}\n")
                f.write(f"- Waterfall snapshots: {len(self.waterfall_log)}\n")
                f.write(f"- Total bytes received: {self.bytes_received}\n\n")
                
                if self.binary_log:
                    binary_sequence = ''.join([str(entry['binary_state']) for entry in self.binary_log])
                    f.write(f"Binary sequence (first 100 bits):\n")
                    f.write(f"{binary_sequence[:100]}\n\n")
                    
                    # Basic statistics
                    ones_count = binary_sequence.count('1')
                    zeros_count = binary_sequence.count('0')
                    f.write(f"Binary Statistics:\n")
                    f.write(f"- Total bits: {len(binary_sequence)}\n")
                    f.write(f"- Ones: {ones_count} ({ones_count/len(binary_sequence)*100:.1f}%)\n")
                    f.write(f"- Zeros: {zeros_count} ({zeros_count/len(binary_sequence)*100:.1f}%)\n")
            
            exported_files.append(summary_file)
            
            file_list = '\n'.join(exported_files)
            messagebox.showinfo("Success", f"All data exported to:\n{file_list}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data:\n{e}")
    
    def run(self):
        """Run the GUI application"""
        try:
            root = self.create_gui()
            
            # Handle window closing
            def on_closing():
                self.stop_stream()
                if self.plot_update_timer:
                    root.after_cancel(self.plot_update_timer)
                root.destroy()
            
            root.protocol("WM_DELETE_WINDOW", on_closing)
            root.mainloop()
            
        except Exception as e:
            print(f"GUI Error: {e}")
            import traceback
            traceback.print_exc()

# Example usage and stream URLs
def main():
    """Main application entry point"""
    
    print("🔊 UVB-76 Live Stream Decoder")
    print("=" * 35)
    print()
    print("This application will:")
    print("• Stream live audio from internet radio")
    print("• Analyze frequency in real-time")
    print("• Decode frequency states to binary")
    print("• Display patterns and potential messages")
    print()
    print("Popular UVB-76 stream sources:")
    print("• WebSDR Netherlands: http://websdr.ewi.utwente.nl:8901/")
    print("• KiwiSDR network: http://rx.linkfanel.net/")
    print("• SDR.hu: https://sdr.hu/")
    print()
    print("Note: You may need to find the direct audio stream URL")
    print("      (look for .mp3 or .wav endpoints)")
    
    # Create and run the decoder
    decoder = UVB76StreamDecoder()
    decoder.run()

if __name__ == "__main__":
    main()
