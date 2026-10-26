import matplotlib.pyplot as plt
import matplotlib.patches as patches

def generate_colorful_architecture_diagram(output_path="docs/architecture_diagram.png"):
    fig, ax = plt.subplots(figsize=(16, 10.2), dpi=300)
    fig.patch.set_facecolor('#0B1120')  # Deep dark navy slate
    ax.set_facecolor('#0B1120')

    # Color Palette
    c_indigo = '#6366F1'
    c_orange = '#F97316'
    c_emerald = '#10B981'
    c_cyan = '#06B6D4'
    c_violet = '#8B5CF6'
    c_rose = '#F43F5E'
    c_amber = '#F59E0B'
    c_blue = '#38BDF8'

    # Title Banner
    ax.text(8.0, 9.75, "CartCheck: Distributed Real-Time Architecture & Intelligence Pipeline", 
            fontsize=20, fontweight='bold', color='#F8FAFC', ha='center', va='center')
    ax.text(8.0, 9.4, "Pre-Checkout ML Return Risk Classification • Sub-15ms Latency • Apache Kafka • FastAPI • LightGBM • Streamlit", 
            fontsize=11.5, color='#94A3B8', ha='center', va='center', style='italic')

    # Helper function to draw rounded boxes
    def draw_card(x, y, w, h, bg_color, border_color, title, subtitle="", badge=""):
        rect = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.12,rounding_size=0.22",
            facecolor=bg_color,
            edgecolor=border_color,
            linewidth=2.2,
            zorder=2
        )
        ax.add_patch(rect)
        
        # Badge
        if badge:
            badge_rect = patches.FancyBboxPatch(
                (x + 0.3, y + h - 0.45), 0.9, 0.32,
                boxstyle="round,pad=0.04,rounding_size=0.08",
                facecolor=border_color,
                edgecolor=border_color,
                zorder=3
            )
            ax.add_patch(badge_rect)
            ax.text(x + 0.75, y + h - 0.29, badge, fontsize=8, fontweight='bold', color='#0B1120', ha='center', va='center', zorder=4)
            ax.text(x + 1.35, y + h - 0.29, title, fontsize=12, fontweight='bold', color='#FFFFFF', va='center', zorder=3)
        else:
            ax.text(x + 0.35, y + h - 0.29, title, fontsize=12, fontweight='bold', color='#FFFFFF', va='center', zorder=3)
            
        if subtitle:
            ax.text(x + 0.35, y + h - 0.65, subtitle, fontsize=9.2, color='#CBD5E1', va='top', zorder=3, linespacing=1.45)

    # Helper function for arrows
    def draw_arrow(x1, y1, x2, y2, color, label="", rad=0.0):
        connectionstyle = f"arc3,rad={rad}" if rad != 0.0 else "arc3"
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="-|>",
                color=color,
                lw=2.4,
                mutation_scale=17,
                shrinkA=4,
                shrinkB=4,
                connectionstyle=connectionstyle
            ),
            zorder=4
        )
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if rad != 0.0:
                my += 0.25 * rad * 2
            ax.text(mx, my + 0.15, label, fontsize=8.5, fontweight='bold', color=color, 
                    ha='center', va='bottom', bbox=dict(boxstyle="round,pad=0.2", facecolor='#1E293B', edgecolor=color, lw=1.2), zorder=5)

    # 1. Ingestion Layer (Left)
    draw_card(0.6, 6.4, 3.4, 2.6, '#1E1B4B', c_indigo, "Ingestion & Traffic", 
              "• Holdout Test Dataset (1M Rows)\n• Multi-Item Cart Grouping Engine\n• Kafka Producer Microservice\n• Rate-Throttled Event Dispatch", "DATA")

    # 2. Broker Layer (Middle-Left)
    draw_card(4.7, 6.4, 3.4, 2.6, '#431407', c_orange, "Message Streaming", 
              "• Apache Kafka 7.5.0 Cluster\n• Topic: 'live_cart_events'\n• Apache Zookeeper 7.5.0\n• Partition Durability & Zero Loss", "QUEUE")

    # 3. Inference Layer (Middle-Right)
    draw_card(8.8, 6.4, 3.4, 2.6, '#064E3B', c_emerald, "ML Inference Engine", 
              "• Vectorized Feature Pipeline\n• LightGBM GBDT (AUC: 0.942)\n• Batch Model Scoring (<4.2ms)\n• In-Memory Alert & Metrics Buffers", "ML")

    # 4. Serving Layer (Right)
    draw_card(12.8, 6.4, 3.0, 2.6, '#0C4A6E', c_cyan, "Async Serving API", 
              "• FastAPI Async Event Loop\n• Server-Sent Events (SSE)\n• Non-Blocking /stream Feed\n• Live /health Telemetry Probe", "API")

    # Arrows between top pipeline
    draw_arrow(4.0, 7.7, 4.7, 7.7, c_indigo, "JSON Carts")
    draw_arrow(8.1, 7.7, 8.8, 7.7, c_orange, "Kafka Poll")
    draw_arrow(12.2, 7.7, 12.8, 7.7, c_emerald, "Scored Alerts")

    # 5. Live UI Dashboard (Bottom-Left)
    draw_card(0.6, 1.2, 6.5, 4.5, '#3B0764', c_violet, "Live Cart Inspector (Streamlit Operator UI)", 
              "• Non-Blocking Background Listener Daemon Thread\n• Thread-Safe Deque Buffer & Fast Fragment Refresh (500ms)\n• 'Pause Live Feed' State Preservation Control Toggle\n• Top Metric KPIs: Events/Sec, Total Processed, Alerts\n• 5-Cart Rolling FIFO Feed (Newest Carts at Top)", "UI")

    # Clean routed connection from Serving API to UI Dashboard (L-shaped orthogonal route)
    ax.plot([14.3, 14.3, 3.8, 3.8], [6.4, 6.0, 6.0, 5.7], color=c_cyan, lw=2.4, zorder=4)
    ax.annotate(
        "", xy=(3.8, 5.7), xytext=(3.8, 5.78),
        arrowprops=dict(arrowstyle="-|>", color=c_cyan, lw=2.4, mutation_scale=18),
        zorder=5
    )
    ax.text(9.0, 6.0, "SSE Event Stream (/stream)", fontsize=8.5, fontweight='bold', color=c_cyan, 
            ha='center', va='center', bbox=dict(boxstyle="round,pad=0.25", facecolor='#1E293B', edgecolor=c_cyan, lw=1.2), zorder=6)

    # 6. Advanced 5-Tier Reasoning Logic Tree (Bottom-Right)
    draw_card(7.8, 1.2, 8.0, 4.5, '#1E293B', c_rose, "Multi-Tier Risk Heuristics & Boxed Layout", 
              "", "LOGIC")

    # Inner boxes for the 5 reasons inside card 6
    reasons = [
        ("1. Bracket Buying Detected", "dup_variants >= 2", c_rose, "Multiple sizes/colors to keep only 1"),
        ("2. New Account Anomaly", "account_age < 30 days", c_amber, "Hit-and-Run / Single-event profile"),
        ("3. Historically Volatile SKU", "prod_return_rate > 30%", c_orange, "Product sizing / fabric / defect risk"),
        ("4. Buyer's Remorse Risk", "cart_total_value > $500", c_cyan, "High cart exposure / post-purchase regret"),
        ("5. Serial Returner Profile", "else (User return history)", c_emerald, "Habitual return velocity across past orders")
    ]

    for i, (rtitle, rcond, rcolor, rdesc) in enumerate(reasons):
        ry = 4.65 - (i * 0.68)
        r_rect = patches.FancyBboxPatch(
            (8.1, ry), 7.4, 0.54,
            boxstyle="round,pad=0.06,rounding_size=0.12",
            facecolor='#0B1120',
            edgecolor=rcolor,
            linewidth=1.6,
            zorder=3
        )
        ax.add_patch(r_rect)
        ax.text(8.3, ry + 0.27, f"{rtitle}", fontsize=9.5, fontweight='bold', color=rcolor, va='center', zorder=4)
        ax.text(11.5, ry + 0.27, f"[{rcond}]", fontsize=8.5, color='#F1F5F9', va='center', zorder=4)
        ax.text(13.6, ry + 0.27, rdesc, fontsize=7.8, color='#94A3B8', va='center', zorder=4)

    # Boxed Layout Legend at the bottom of card 6
    ax.text(8.15, 1.5, "Boxed Item Presentation:", fontsize=9, fontweight='bold', color='#FFFFFF', zorder=3)
    
    # Safe box indicator
    box_safe = patches.FancyBboxPatch((10.15, 1.35), 2.3, 0.38, boxstyle="round,pad=0.05,rounding_size=0.1",
                                       facecolor='#1E293B', edgecolor='#94A3B8', lw=1.3, zorder=3)
    ax.add_patch(box_safe)
    ax.text(11.3, 1.54, "[SAFE] Neutral Border Card", fontsize=8, color='#E2E8F0', ha='center', va='center', zorder=4)

    # Flagged box indicator
    box_flag = patches.FancyBboxPatch((12.75, 1.35), 2.7, 0.38, boxstyle="round,pad=0.05,rounding_size=0.1",
                                       facecolor='#0C4A6E', edgecolor='#38BDF8', lw=1.6, zorder=3)
    ax.add_patch(box_flag)
    ax.text(14.1, 1.54, "[FLAG] Blue st.info Callout Box", fontsize=8, color='#38BDF8', fontweight='bold', ha='center', va='center', zorder=4)

    # Arrow from UI to Reasoning
    draw_arrow(7.1, 3.45, 7.8, 3.45, c_violet, "Evaluate Items (Risk >= 80%)")

    ax.set_xlim(0, 16.5)
    ax.set_ylim(0.5, 10.3)
    ax.axis('off')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#0B1120')
    plt.close()
    print(f"Colorful architecture diagram successfully generated and saved to {output_path}")

if __name__ == "__main__":
    generate_colorful_architecture_diagram()
