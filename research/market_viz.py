import matplotlib.pyplot as plt
import seaborn as sns
import io
import os
import random
import datetime

# Set style
sns.set_theme(style="darkgrid")
plt.rcParams['figure.figsize'] = [10, 6]
plt.rcParams['figure.dpi'] = 100

class MarketViz:
    def generate_chart(self, title: str, data_points: list, labels: list, filename: str = "chart.png") -> str:
        """
        Generate a chart and save it to a temporary file.
        Returns the absolute path to the file.
        """
        try:
            plt.figure()
            
            # Create a mock time series if only single points provided
            if len(data_points) < 2:
                # Generate a mock 7-day trend ending at the data point
                base = data_points[0] if data_points else 50
                data_points = [base + random.uniform(-10, 10) for _ in range(6)] + [base]
                labels = [(datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%m-%d") for i in range(7)][::-1]

            # Plot
            sns.lineplot(x=labels, y=data_points, marker="o", linewidth=2.5, color="#00ff00")
            
            plt.title(title, fontsize=16, fontweight='bold')
            plt.ylabel("Probability (%)", fontsize=12)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Save
            path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "temp", filename))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            plt.savefig(path)
            plt.close()
            
            return path
        except Exception as e:
            print(f"Chart generation failed: {e}")
            return None

viz = MarketViz()
