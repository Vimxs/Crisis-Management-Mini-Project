# Crisis Response Intelligence System

### Data-Driven Emergency Resource Allocation & Response Prioritization

A decision-support system for prioritizing multiple simultaneous emergency incidents and recommending the allocation of limited emergency resources using crisis conditions, geospatial information, environmental data, and resource constraints.

---

##  Overview

During large-scale emergencies, multiple incidents can occur simultaneously while response agencies operate with limited ambulances, rescue teams, medical resources, shelters, and response time.

The **Crisis Response Intelligence System (CRIS)** is designed to address the decision-making layer of emergency response:

- Which incident requires immediate attention?
- Which available resource should be deployed first?
- How should changing severity, impact, urgency, vulnerability, and accessibility affect incident priority?
- How can limited resources be allocated while considering availability, capacity, compatibility, and travel time?

The system combines heterogeneous crisis information into an interpretable workflow:

**DATA → PROCESS → PRIORITIZE → ALLOCATE → VISUALIZE**

>  This is an academic decision-support prototype. The system is not intended to autonomously control emergency operations. Final decisions remain subject to review by authorized emergency-response personnel.

---

# Objectives

The project aims to:

- Collect and integrate emergency, environmental, demographic, and geospatial data.
- Process and validate heterogeneous datasets.
- Generate meaningful incident-level features.
- Estimate hazard/risk where machine learning is applicable.
- Calculate a dynamic and explainable priority score.
- Rank simultaneous incidents according to response priority.
- Match available emergency resources with prioritized incidents.
- Consider resource compatibility, availability, capacity, distance, and accessibility.
- Provide an interactive command dashboard for emergency-response decision support.

---

# Problem Statement

Emergency agencies may face multiple simultaneous incidents while operating under limited resources.

Traditional systems can provide useful capabilities such as:

- Monitoring
- GIS mapping
- Routing
- Risk assessment
- Prediction
- Optimization

However, these capabilities do not necessarily answer the combined operational question:

> **"Given multiple active incidents and limited resources, which incident should be handled first and which resource should be assigned?"**

CRIS focuses on this decision layer by combining incident conditions with resource constraints to generate dynamic priorities and allocation recommendations.

---

# Proposed Solution

The proposed system combines:

- Incident severity
- Affected population / impact
- Urgency
- Vulnerability
- Accessibility
- Resource availability

These inputs are processed by a **Dynamic Priority Engine**, followed by a **Resource Allocation Engine**, and finally presented through an **Emergency Response Dashboard**.

### High-Level Workflow

```text
                    ┌──────────────────────┐
                    │   External Data      │
                    │ Weather / GIS /      │
                    │ Population / etc.    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Crisis Data Ingestion│
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Data Processing &    │
                    │ Validation            │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    ▼                      ▼
          ┌─────────────────┐    ┌─────────────────┐
          │ Hazard / Risk   │    │ Incident &      │
          │ Prediction      │    │ Resource Data   │
          │ ML Component    │    │                 │
          └────────┬────────┘    └────────┬────────┘
                   │                      │
                   └──────────┬───────────┘
                              ▼
                   ┌──────────────────────┐
                   │ Dynamic Priority     │
                   │ Engine               │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │ Resource Allocation  │
                   │ Engine               │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │ Command Dashboard    │
                   └──────────────────────┘
