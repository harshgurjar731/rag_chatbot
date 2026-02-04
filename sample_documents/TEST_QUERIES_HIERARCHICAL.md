# Titan-7 Hierarchical Test Queries
*Demonstrating Primary vs. Secondary Source Logic*

This document outlines queries designed to test the 2-stage retrieval:
1.  **Stage 1 (Main Doc)**: Get a high-level summary from `Titan7_Overview_and_Policy`.
2.  **Stage 2 (Intent)**: Detect a specific intent (e.g., `lithography_process`) leading to a specialized document.

## 1. Intent: `lithography_process`
**Goal**: User asks about the specific machine or parameters.
*   **Query**: "What is the exposure dose for the Titan-7 lithography process?"
    *   **Main Doc Answer** (Expected): "We utilize EUV lithography to define the 5nm transistor gates. This is the most critical step... Precision alignment is key."
    *   **Detected Intent**: `lithography_process`
    *   **Secondary Source**: `Titan7_Lithography_Specs.pdf`
    *   **Deep Dive Answer**: "Dose Energy: 45 mJ/cm² +/- 2%".

*   **Query**: "Which photoresist do we use for the 5nm gates?"
    *   **Main Doc Answer**: (Generic info about process modules).
    *   **Detected Intent**: `lithography_process` / `euv_specs`
    *   **Deep Dive Answer**: "TOK-7705 Positive Tone, Thickness: 35 nm".

## 2. Intent: `defect_analysis`
**Goal**: User encounters a quality issue and needs debugging protocols.
*   **Query**: "How do I analyze a D-707 pattern collapse defect?"
    *   **Main Doc Answer**: "Any wafer showing anomalous defect density is immediately quarantined. Analyzing these defects requires High-Res SEM."
    *   **Detected Intent**: `defect_analysis`
    *   **Secondary Source**: `Titan7_Defect_Analysis_Protocols.pdf`
    *   **Deep Dive Answer**: "Root Cause: Aspect Ratio too high / Resist Adhesion. Action: Check Spin Coat."

*   **Query**: "What are the settings for SEM Voltage Contrast mode?"
    *   **Main Doc Answer**: (Generic mention of SEM).
    *   **Detected Intent**: `sem_protocols`
    *   **Deep Dive Answer**: "Beam Energy: 800V. Contrast: High. Floating gates appear dark."

## 3. General Overview (No Specific Intent)
**Goal**: User asks a general question that DOES NOT require a deep dive.
*   **Query**: "What is the safety classification for Fab 42?"
    *   **Main Doc Answer**: "Fab 42 operates as a Class 1 Cleanroom. Full bunny suits required."
    *   **Detected Intent**: `general_qa` (or None)
    *   **Secondary Source**: N/A (Answer is efficient and complete in Main Doc).

## 4. Why this matters?
This structure prevents the "No Context Found" error. The **Overview** document ensures broad coverage of keywords (Lithography, Defect, Safety), while the **Specialized** documents provide the numeric precision required by engineers, only when needed.
