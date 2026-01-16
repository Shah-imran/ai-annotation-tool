# Project Architecture Diagrams

## System Overview

```mermaid
graph TB
    subgraph "YOLO ANNOTATION ECOSYSTEM"
        subgraph "Input Layer"
            A[Raw Images]
            B[Existing Annotations]
            C[Class Definitions]
        end

        subgraph "Processing Layer"
            D[Annotation Tool (Scan Lab)<br/>MVC Architecture]
            E[Analysis Scripts<br/>Python Tools]
        end

        subgraph "Output Layer"
            F[New Annotations<br/>YOLO Format]
            G[Visualizations<br/>PNG Charts]
            H[Reports<br/>Excel Files]
        end

        subgraph "Storage Layer"
            I[File System<br/>Images + Annotations]
            J[Analysis Results<br/>Charts + Reports]
        end
    end

    A --> D
    B --> E
    C --> D
    C --> E

    D --> F
    E --> G
    E --> H

    F --> I
    G --> J
    H --> J

    style D fill:#f3e5f5
    style E fill:#e1f5fe
    style I fill:#fff3e0
```

## Annotation Tool (Scan Lab) MVC Architecture

```mermaid
graph LR
    subgraph "Models (Data Layer)"
        M1[BoundingBox<br/>• YOLO coordinates<br/>• Text descriptions<br/>• Format conversion]
        M2[AnnotationModel<br/>• Collection management<br/>• CRUD operations<br/>• File I/O]
        M3[ImageModel<br/>• File loading<br/>• Navigation state<br/>• Path management]
    end

    subgraph "Views (UI Layer)"
        V1[MainWindow<br/>• Menu system<br/>• Layout management<br/>• Dialogs]
        V2[ImageCanvas<br/>• Image display<br/>• Mouse interactions<br/>• Drawing feedback]
        V3[ControlPanel<br/>• Class selection<br/>• Annotation details<br/>• Navigation controls]
    end

    subgraph "Controllers (Logic Layer)"
        C1[MainController<br/>• Application flow<br/>• Component coordination<br/>• File operations]
        C2[AnnotationController<br/>• Annotation CRUD<br/>• Auto-save<br/>• Validation]
    end

    M1 -.-> M2
    M2 -.-> M3

    V1 -.-> V2
    V2 -.-> V3

    C1 -.-> C2

    M2 <--> C2
    M3 <--> C1

    V1 <--> C1
    V2 <--> C2
    V3 <--> C2

    style M1 fill:#ffebee
    style V1 fill:#e3f2fd
    style C1 fill:#f1f8e9
```

## Data Flow Architecture

```mermaid
flowchart TD
    subgraph "User Interactions"
        UI1[Mouse Events]
        UI2[Keyboard Input]
        UI3[Menu Actions]
    end

    subgraph "Signal Processing"
        SP1[View Signals]
        SP2[Controller Handlers]
        SP3[Model Updates]
    end

    subgraph "Data Persistence"
        DP1[YOLO Files]
        DP2[Configuration]
        DP3[Analysis Cache]
    end

    subgraph "Analysis Pipeline"
        AP1[Data Loading]
        AP2[Statistical Analysis]
        AP3[Visualization]
        AP4[Report Generation]
    end

    UI1 --> SP1
    UI2 --> SP1
    UI3 --> SP1

    SP1 --> SP2
    SP2 --> SP3
    SP3 --> DP1

    DP1 --> AP1
    AP1 --> AP2
    AP2 --> AP3
    AP3 --> AP4

    DP2 -.-> SP2
    DP3 -.-> AP2

    style UI1 fill:#e8f5e8
    style SP2 fill:#fff3e0
    style DP1 fill:#f3e5f5
    style AP2 fill:#e1f5fe
```

## Component Interaction Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant V as View
    participant C as Controller
    participant M as Model
    participant F as File System

    U->>V: Draw bounding box
    V->>C: annotation_drawn signal
    C->>M: add_annotation()
    M->>M: validate data
    M->>F: save to .txt file
    M->>V: annotations_changed signal
    V->>V: refresh display
    V->>U: visual feedback

    Note over U,F: Auto-save workflow

    U->>V: Navigate to next image
    V->>C: next_image_requested
    C->>M: load_next_image()
    M->>F: read image file
    M->>F: read annotations
    M->>V: update display
    V->>U: show new image
```

## File System Organization

```mermaid
graph TD
    subgraph "Project Root"
        A[Yolo_mark/]

        subgraph "Annotation Tool (Scan Lab)"
            B[annotation_tool/]
            B1[models/]
            B2[views/]
            B3[controllers/]
            B4[main.py]
        end

        subgraph "Analysis Tools"
            C[analyze_annotations.py]
            C1[plot_*.py scripts]
            C2[prepare_excel.py]
        end

        subgraph "Data"
            D[x64/Release/clean_data/]
            D1[*.jpg images]
            D2[*.txt annotations]
            D3[obj.names classes]
        end

        subgraph "Results"
            E[analysis_results/]
            E1[*.png charts]
            E2[*.xlsx reports]
        end

        subgraph "Legacy"
            F[yolo_mark.py]
            F1[run_yolo_mark.py]
        end
    end

    A --> B
    A --> C
    A --> D
    A --> E
    A --> F

    B --> B1
    B --> B2
    B --> B3
    B --> B4

    C --> C1
    C --> C2

    D --> D1
    D --> D2
    D --> D3

    E --> E1
    E --> E2

    F --> F1

    style B fill:#f3e5f5
    style C fill:#e1f5fe
    style D fill:#fff3e0
    style E fill:#e8f5e8
```

## Technology Stack

```mermaid
graph LR
    subgraph "Frontend (UI)"
        A[PyQt5<br/>GUI Framework]
        A1[QWidget<br/>Custom Components]
        A2[QPainter<br/>Custom Drawing]
        A3[QSignal<br/>Event System]
    end

    subgraph "Backend (Logic)"
        B[Python 3.7+<br/>Core Language]
        B1[OpenCV<br/>Image Processing]
        B2[NumPy<br/>Numerical Computing]
        B3[Pandas<br/>Data Analysis]
    end

    subgraph "Data Storage"
        C[File System<br/>Local Storage]
        C1[YOLO Format<br/>Annotations]
        C2[JSON/Excel<br/>Reports]
        C3[PNG<br/>Visualizations]
    end

    subgraph "Analysis"
        D[Matplotlib<br/>Plotting]
        D1[Seaborn<br/>Statistical Plots]
        D2[Custom Scripts<br/>Domain Logic]
    end

    A --> A1
    A --> A2
    A --> A3

    B --> B1
    B --> B2
    B --> B3

    C --> C1
    C --> C2
    C --> C3

    D --> D1
    D --> D2

    A1 -.-> B
    B1 -.-> C
    B3 -.-> D

    style A fill:#e3f2fd
    style B fill:#f1f8e9
    style C fill:#fff3e0
    style D fill:#f3e5f5
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Development Environment"
        DE1[Source Code<br/>Git Repository]
        DE2[Python Interpreter<br/>3.7+]
        DE3[Dependencies<br/>requirements.txt]
    end

    subgraph "Runtime Environment"
        RE1[Annotation Tool (Scan Lab)<br/>Main Process]
        RE2[File System<br/>Data Storage]
        RE3[OS Integration<br/>File Dialogs]
    end

    subgraph "User Environment"
        UE1[Windows/Linux/Mac<br/>Cross-platform]
        UE2[Mouse + Keyboard<br/>Input Devices]
        UE3[Display<br/>1280x720+ recommended]
    end

    DE1 --> RE1
    DE2 --> RE1
    DE3 --> RE1

    RE1 --> UE1
    RE2 --> UE1
    RE3 --> UE1

    UE2 --> RE1
    UE3 --> RE1

    style DE1 fill:#e1f5fe
    style RE1 fill:#f3e5f5
    style UE1 fill:#e8f5e8
```
