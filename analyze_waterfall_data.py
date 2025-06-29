#!/usr/bin/env python3
"""
UVB-76 Waterfall Data Analysis Tool
Loads and analyzes waterfall data exported from the UVB-76 Stream Decoder
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import pickle
import argparse
from datetime import datetime
import os

class WaterfallAnalyzer:
    def __init__(self, data_file):
        """Initialize the analyzer with a data file
        
        Args:
            data_file: Path to .npz, .pkl, or .csv file from UVB-76 decoder
        """
        self.data_file = data_file
        self.data = None
        self.timestamps = None
        self.frequencies = None
        self.magnitudes = None
        self.metadata = None
        
        # Load the data
        self.load_data()
    
    def load_data(self):
        """Load waterfall data from various file formats"""
        if self.data_file.endswith('.npz'):
            self.load_npz_data()
        elif self.data_file.endswith('.pkl'):
            self.load_pickle_data()
        elif self.data_file.endswith('.csv'):
            self.load_csv_data()
        else:
            raise ValueError(f"Unsupported file format: {self.data_file}")
    
    def load_npz_data(self):
        """Load data from NumPy archive (.npz)"""
        print(f"Loading NumPy archive: {self.data_file}")
        data = np.load(self.data_file, allow_pickle=True)
        
        self.timestamps = data['timestamps']
        self.magnitudes = data['magnitudes']
        
        # Handle different data structures
        if 'frequencies' in data and len(data['frequencies'].shape) > 1:
            # Detailed logging format
            self.frequencies = data['frequencies']
        elif 'waterfall_freqs' in data:
            # Basic format with frequency axis
            self.frequencies = data['waterfall_freqs']
        
        if 'metadata' in data:
            self.metadata = data['metadata'].item()
        
        print(f"Loaded {len(self.timestamps)} time samples")
        print(f"Frequency range: {len(self.frequencies if hasattr(self.frequencies, '__len__') else self.frequencies[0])} bins")
    
    def load_pickle_data(self):
        """Load data from pickle file (.pkl)"""
        print(f"Loading pickle file: {self.data_file}")
        with open(self.data_file, 'rb') as f:
            data = pickle.load(f)
        
        if 'detailed_log' in data and data['detailed_log']:
            # Use detailed log
            detailed = data['detailed_log']
            self.timestamps = np.array([entry['timestamp'] for entry in detailed])
            self.frequencies = np.array([entry['frequencies'] for entry in detailed])
            self.magnitudes = np.array([entry['magnitudes'] for entry in detailed])
        else:
            # Use basic waterfall data
            self.timestamps = np.array(data['waterfall_times'])
            self.magnitudes = np.array(data['waterfall_data'])
            self.frequencies = data['waterfall_frequencies']
        
        self.metadata = data.get('metadata', {})
        print(f"Loaded {len(self.timestamps)} time samples")
    
    def load_csv_data(self):
        """Load data from CSV file (basic implementation)"""
        print(f"Loading CSV file: {self.data_file}")
        import pandas as pd
        
        df = pd.read_csv(self.data_file)
        
        # Group by timestamp
        grouped = df.groupby('Timestamp')
        self.timestamps = np.array(list(grouped.groups.keys()))
        
        # Reconstruct magnitude arrays
        magnitude_list = []
        frequency_list = []
        
        for timestamp in self.timestamps:
            group = grouped.get_group(timestamp)
            magnitude_list.append(group['Magnitude'].values)
            frequency_list.append(group['Frequency_Hz'].values)
        
        self.magnitudes = np.array(magnitude_list)
        self.frequencies = np.array(frequency_list)
        
        print(f"Loaded {len(self.timestamps)} time samples from CSV")
    
    def plot_waterfall(self, freq_range=None, time_range=None, save_plot=False):
        """Plot the waterfall display
        
        Args:
            freq_range: Tuple of (min_freq, max_freq) in Hz
            time_range: Tuple of (start_time, end_time) in seconds from start
            save_plot: Whether to save the plot as PNG
        """
        if self.magnitudes is None:
            print("No data loaded!")
            return
        
        print("Creating waterfall plot...")
        
        # Prepare data
        if len(self.magnitudes.shape) == 1:
            # Single spectrum - duplicate for visualization
            plot_data = np.array([self.magnitudes])
            plot_times = np.array([0])
            plot_freqs = self.frequencies
        else:
            plot_data = self.magnitudes
            plot_times = self.timestamps - self.timestamps[0]  # Relative time
            plot_freqs = self.frequencies[0] if len(self.frequencies.shape) > 1 else self.frequencies
        
        # Apply frequency range filter
        if freq_range:
            freq_mask = (plot_freqs >= freq_range[0]) & (plot_freqs <= freq_range[1])
            plot_freqs = plot_freqs[freq_mask]
            plot_data = plot_data[:, freq_mask]
        
        # Apply time range filter  
        if time_range:
            time_mask = (plot_times >= time_range[0]) & (plot_times <= time_range[1])
            plot_times = plot_times[time_mask]
            plot_data = plot_data[time_mask, :]
        
        # Create the plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), height_ratios=[3, 1])
        
        # Waterfall plot
        extent = [plot_freqs[0], plot_freqs[-1], plot_times[-1], plot_times[0]]
        
        # Use log scale for better visibility
        plot_data_log = np.log10(np.maximum(plot_data, 1e-10))
        
        # Custom colormap
        colors = ['#000033', '#000066', '#0000CC', '#0066FF', '#00CCFF', '#66FFCC', '#CCFF66', '#FFCC00', '#FF6600', '#FF0000']
        n_bins = 256
        cmap = LinearSegmentedColormap.from_list('waterfall', colors, N=n_bins)
        
        im = ax1.imshow(plot_data_log, aspect='auto', extent=extent, cmap=cmap, interpolation='nearest')
        ax1.set_xlabel('Frequency (Hz)')
        ax1.set_ylabel('Time (seconds)')
        ax1.set_title('UVB-76 Waterfall Display')
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax1)
        cbar.set_label('Magnitude (log10)')
        
        # Average spectrum plot
        avg_spectrum = np.mean(plot_data, axis=0)
        ax2.plot(plot_freqs, avg_spectrum, 'b-', linewidth=1)
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Average Magnitude')
        ax2.set_title('Average Spectrum')
        ax2.grid(True, alpha=0.3)
        
        # Mark UVB-76 frequencies if in range
        uvb76_freqs = [21.53, 26.92, 32.30]
        for freq in uvb76_freqs:
            if plot_freqs[0] <= freq <= plot_freqs[-1]:
                ax1.axvline(freq, color='red', linestyle='--', alpha=0.7, linewidth=1)
                ax2.axvline(freq, color='red', linestyle='--', alpha=0.7, linewidth=1)
                ax2.text(freq, max(avg_spectrum)*0.9, f'{freq}Hz', rotation=90, 
                        verticalalignment='top', color='red', fontsize=8)
        
        plt.tight_layout()
        
        if save_plot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"waterfall_analysis_{timestamp}.png"
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            print(f"Plot saved as: {filename}")
        
        plt.show()
    
    def analyze_signal_strength(self, target_freq=None):
        """Analyze signal strength over time
        
        Args:
            target_freq: Specific frequency to analyze (Hz)
        """
        if self.magnitudes is None:
            print("No data loaded!")
            return
        
        print("\n=== Signal Strength Analysis ===")
        
        # Overall statistics
        total_samples = len(self.timestamps)
        duration = self.timestamps[-1] - self.timestamps[0] if len(self.timestamps) > 1 else 0
        
        print(f"Total time samples: {total_samples}")
        print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        
        if hasattr(self.metadata, '__getitem__') and 'sample_rate' in self.metadata:
            print(f"Sample rate: {self.metadata['sample_rate']} Hz")
        
        # Frequency analysis
        if len(self.magnitudes.shape) > 1:
            avg_spectrum = np.mean(self.magnitudes, axis=0)
            plot_freqs = self.frequencies[0] if len(self.frequencies.shape) > 1 else self.frequencies
            
            # Find peak frequencies
            peak_indices = np.argsort(avg_spectrum)[-10:]  # Top 10 peaks
            print(f"\nTop 10 frequencies by average magnitude:")
            for i, idx in enumerate(reversed(peak_indices)):
                freq = plot_freqs[idx]
                mag = avg_spectrum[idx]
                print(f"  {i+1}: {freq:.2f} Hz - Magnitude: {mag:.2f}")
            
            # UVB-76 specific analysis
            uvb76_freqs = [21.53, 26.92, 32.30]
            print(f"\nUVB-76 frequency analysis:")
            for freq in uvb76_freqs:
                # Find closest frequency bin
                freq_diffs = np.abs(plot_freqs - freq)
                closest_idx = np.argmin(freq_diffs)
                closest_freq = plot_freqs[closest_idx]
                avg_mag = avg_spectrum[closest_idx]
                
                print(f"  {freq} Hz: Closest bin {closest_freq:.2f} Hz, Avg magnitude: {avg_mag:.2f}")
        
        # Time series analysis if specific frequency requested
        if target_freq and len(self.magnitudes.shape) > 1:
            plot_freqs = self.frequencies[0] if len(self.frequencies.shape) > 1 else self.frequencies
            freq_diffs = np.abs(plot_freqs - target_freq)
            target_idx = np.argmin(freq_diffs)
            
            time_series = self.magnitudes[:, target_idx]
            rel_times = self.timestamps - self.timestamps[0]
            
            plt.figure(figsize=(12, 6))
            plt.plot(rel_times, time_series, 'b-', linewidth=1)
            plt.xlabel('Time (seconds)')
            plt.ylabel('Magnitude')
            plt.title(f'Signal Strength Over Time at {plot_freqs[target_idx]:.2f} Hz')
            plt.grid(True, alpha=0.3)
            plt.show()
    
    def export_summary(self, output_file=None):
        """Export analysis summary to text file"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"waterfall_analysis_{timestamp}.txt"
        
        with open(output_file, 'w') as f:
            f.write("UVB-76 Waterfall Data Analysis Summary\n")
            f.write("=" * 40 + "\n\n")
            
            f.write(f"Source file: {self.data_file}\n")
            f.write(f"Analysis time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if self.metadata:
                f.write("Metadata:\n")
                for key, value in self.metadata.items():
                    f.write(f"  {key}: {value}\n")
                f.write("\n")
            
            if self.timestamps is not None:
                f.write(f"Time samples: {len(self.timestamps)}\n")
                if len(self.timestamps) > 1:
                    duration = self.timestamps[-1] - self.timestamps[0]
                    f.write(f"Duration: {duration:.1f} seconds\n")
                    f.write(f"Start time: {datetime.fromtimestamp(self.timestamps[0])}\n")
                    f.write(f"End time: {datetime.fromtimestamp(self.timestamps[-1])}\n")
            
            if self.frequencies is not None:
                f.write(f"Frequency bins: {len(self.frequencies) if hasattr(self.frequencies, '__len__') else 'Variable'}\n")
            
            if hasattr(self, 'magnitudes') and self.magnitudes is not None:
                f.write(f"Data shape: {self.magnitudes.shape}\n")
        
        print(f"Analysis summary saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Analyze UVB-76 waterfall data")
    parser.add_argument("data_file", help="Path to waterfall data file (.npz, .pkl, or .csv)")
    parser.add_argument("--freq-range", nargs=2, type=float, metavar=("MIN", "MAX"),
                       help="Frequency range to analyze (Hz)")
    parser.add_argument("--time-range", nargs=2, type=float, metavar=("START", "END"),
                       help="Time range to analyze (seconds from start)")
    parser.add_argument("--target-freq", type=float, help="Analyze specific frequency (Hz)")
    parser.add_argument("--save-plot", action="store_true", help="Save waterfall plot as PNG")
    parser.add_argument("--export-summary", action="store_true", help="Export analysis summary")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.data_file):
        print(f"Error: File {args.data_file} not found!")
        return
    
    try:
        # Create analyzer
        analyzer = WaterfallAnalyzer(args.data_file)
        
        # Create waterfall plot
        analyzer.plot_waterfall(
            freq_range=args.freq_range,
            time_range=args.time_range,
            save_plot=args.save_plot
        )
        
        # Analyze signal strength
        analyzer.analyze_signal_strength(target_freq=args.target_freq)
        
        # Export summary if requested
        if args.export_summary:
            analyzer.export_summary()
        
    except Exception as e:
        print(f"Error analyzing data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 