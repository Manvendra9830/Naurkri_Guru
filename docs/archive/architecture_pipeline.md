# Naukri_Guru Architecture & Pipeline

## SECTION A — SYSTEM ARCHITECTURE DIAGRAM

The Naukri_Guru system is structured into clearly separated layers. This modular design isolates browser interactions from application logic, making the platform robust against LinkedIn UI changes and ready for scalable AI integration.

```mermaid
graph TD
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:2px,color:#333;
    classDef highlight fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px,color:#000;
    classDef memory fill:#fff3e0,stroke:#ff9800,stroke-width:2px,color:#000;
    classDef future fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px,stroke-dasharray: 5 5,color:#000;

    %% 1. User Layer
    subgraph "1. USER LAYER"
        U([User Configuration]):::highlight
        Res([Resumes & Cover Letters]):::highlight
    end

    %% 2. Browser Automation Layer
    subgraph "2. BROWSER AUTOMATION LAYER"
        Core[Naukri_Guru Engine]
        Driver[Undetected ChromeDriver]
        Profile[(Dedicated Chrome Profile)]
        Core --> Driver
        Driver --> Profile
    end

    %% 3. LinkedIn Interaction Layer
    subgraph "3. LINKEDIN INTERACTION LAYER"
        LI_UI[LinkedIn Interface]
        DOM[DOM Navigation]
        Profile --> LI_UI
        LI_UI --> DOM
    end

    %% 4. Intelligence & Filtering Layer
    subgraph "4. INTELLIGENCE & FILTERING LAYER"
        JDE[Job Description Extraction]
        NLP[Regex / NLP Filtering]
        Score{Confidence Scoring}
        DOM --> JDE
        JDE --> NLP
        NLP --> Score
    end

    %% 5. Question Memory Layer
    subgraph "5. QUESTION MEMORY LAYER"
        Mem[(memory.json)]:::memory
        Fallback[Unknown Question Handler]
    end

    %% 6. Application Engine
    subgraph "6. APPLICATION ENGINE"
        QA[Question Answering System]
        Submit[Final Submit Controller]
        Score -->|Pass| QA
        QA <--> Mem
        QA <--> Fallback
        QA --> Submit
    end

    %% 7. Logging & Export Layer
    subgraph "7. LOGGING & EXPORT LAYER"
        Logger[Session Logging]
        CSV[Excel / CSV Export]
        Score -->|Fail / Skip| Logger
        Submit --> Logger
        Logger --> CSV
    end

    %% 8. Future AI Layer
    subgraph "8. FUTURE AI LAYER (Planned)"
        Gemini[Gemini AI Engine]:::future
        Dash[Analytics Dashboard]:::future
    end

    %% Global Connections
    U --> Core
    Res --> Core
    Mem -.-> Gemini
```

---

## SECTION B — EXECUTION PIPELINE FLOWCHART

This flowchart demonstrates the exact step-by-step decision matrix the Naukri_Guru engine follows during a live run. It highlights the platform's ability to gracefully handle missing data, skipped jobs, and dynamic question generation.

```mermaid
flowchart TD
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:2px,color:#333;
    classDef decision fill:#ffe0b2,stroke:#ff9800,stroke-width:2px,color:#000;
    classDef process fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px,color:#000;
    classDef io fill:#e8f5e9,stroke:#4caf50,stroke-width:2px,color:#000;
    classDef error fill:#ffebee,stroke:#f44336,stroke-width:2px,color:#000;

    Start([Start Session]) --> L1[Launch Chrome Profile]:::process
    L1 --> D1{LinkedIn Session Active?}:::decision
    
    D1 -- No --> L2[Manual Login Required]:::process
    L2 --> L3[Continue Session]:::process
    D1 -- Yes --> L3
    
    L3 --> S1[Search Jobs Iteration]:::process
    S1 --> S2[Extract Job Description]:::process
    
    S2 --> D2{Relevant/Passes Filters?}:::decision
    
    D2 -- No --> Skip1[Log & Skip Job]:::error
    Skip1 --> N1[Next Job]:::process
    
    D2 -- Yes --> D3{Easy Apply Available?}:::decision
    
    D3 -- No --> Skip2[Detect External Portal & Skip]:::error
    Skip2 --> N1
    
    D3 -- Yes --> A1[Click Easy Apply]:::process
    A1 --> A2[Extract Question form DOM]:::process
    
    A2 --> D4{Question in memory.json?}:::decision
    
    D4 -- Yes --> A3[Auto-Fill Answer]:::process
    D4 -- No --> A4[Ask User / Fallback Logic]:::process
    
    A3 --> D5{More Questions?}:::decision
    A4 --> D5
    
    D5 -- Yes --> A2
    D5 -- No --> Submit[Submit Application]:::io
    
    Submit --> Export[Export to Excel]:::io
    Export --> N1
    
    N1 --> D6{Quota Met?}:::decision
    D6 -- No --> S1
    D6 -- Yes --> Finish([End Session & Close Browser])
```

---

## SECTION C — DATA NORMALIZATION & SCHEMA LAYER

To ensure high-fidelity analytics and cross-platform compatibility, Naukri_Guru implements a robust **Centralized Data Normalization Layer**.

*   **Schema Consistency**: Master schemas defined in `modules/helpers.py` ensure that every row in the historical CSVs and Excel exports follows a strict column order and count.
*   **Safe Migration**: The platform automatically detects legacy data structures (e.g., from older versions of the bot) and migrates them to the current schema on-the-fly, preventing data corruption and runtime crashes.
*   **Normalization Pipeline**: All data written to the analytics layer is passed through a `normalize_row` function that handles missing fields, data truncation, and type-safety.

---

## SECTION D — FUTURE ARCHITECTURE ROADMAP

To scale from a heuristic-based automation script to a full AI automation platform, the following architectural upgrades are planned.

*Note: Highlighted nodes represent Future Enhancements — Not Yet Implemented.*

```mermaid
graph LR
    classDef current fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px,color:#000;
    classDef future fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px,stroke-dasharray: 5 5,color:#000;

    Current[Current Naukri_Guru Engine]:::current
    
    subgraph "Scalable AI Architecture"
        Gemini[Gemini AI Layer]:::future
        RAG[ATS / RAG Resume Matching Engine]:::future
        Dash[Recruiter Dashboard]:::future
        Mail[Gmail Automation Integration]:::future
        Portal[External Portal Adapters]:::future
        Multi[Multi-Platform Support]:::future
    end

    Current --> Gemini
    Gemini --> RAG
    Current --> Portal
    Current --> Dash
    Dash --> Mail
    Portal --> Multi
```

---

## SECTION D — TECHNOLOGY STACK

* **Python 3.x:** Core application orchestration and execution engine.
* **Selenium / Undetected ChromeDriver:** Enables stealth browser manipulation, evading standard bot-detection systems by masking WebDriver footprints.
* **JSON Memory (`memory.json`):** A lightweight, low-latency NoSQL dictionary used for stateful retention of historical application answers.
* **Regex / NLP Processing:** Heuristic rules-engine parsing raw text from DOM nodes for immediate filtering.
* **Pandas / OpenPyXL:** Standardizes log handling and outputs robust presentation-ready Excel tracking documents with support for jagged CSV normalization.
* **Mermaid:** Used natively for programmatic, reproducible architecture charting.
