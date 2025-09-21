Of course. I will act as your expert business analyst and software architect. Based on the provided Jira project issues for **{project_key}**, I will now perform a comprehensive analysis and generate the required documentation.

***Note:** Since the actual `{project_issues}` data was not provided in your placeholder prompt, I will generate a sample analysis based on a hypothetical but common scenario: a project to build a "Customer Feedback and Analytics Portal." This will demonstrate the structure, depth, and methodology you can expect when real data is supplied. Please replace the hypothetical content with your actual project data for a precise analysis.*

---

### **Part 1: Complete Requirements Document**

# Requirements Document for Project FDBK

## 1. Executive Summary
The Customer Feedback and Analytics Portal (FDBK) aims to consolidate customer feedback from multiple sources (Zendesk, App Store reviews, in-app forms) into a single, powerful platform. The primary objective is to empower product managers, customer support teams, and executives with actionable insights through automated sentiment analysis, trend identification, and customizable dashboards. This system will replace manual data aggregation processes, reduce insight latency from weeks to real-time, and directly contribute to more data-driven product development and customer satisfaction improvements.

## 2. Project Scope
**In-Scope:**
*   Development of a central data ingestion API for various feedback sources.
*   Implementation of a sentiment analysis engine (initially for English text).
*   Creation of a web-based dashboard with role-based access control (Admin, PM, Support Agent).
*   Functionality to tag, categorize, and filter feedback items.
*   Generation of trend reports and visualizations (charts, graphs, word clouds).
*   User management and authentication system.
*   RESTful API for potential future integrations.

**Out-of-Scope:**
*   Development of mobile applications (iOS/Android) for the portal.
*   Real-time chat or communication features between users within the portal.
*   Direct integration with financial or ERP systems.
*   Sentiment analysis for languages other than English in the initial release (Phase 2).
*   Automated action-taking based on feedback (e.g., auto-creating Jira tickets, though API for manual creation is in-scope).

## 3. Functional Requirements
**FR1: Data Ingestion Module**
*   FR1.1: The system shall provide a secure REST API endpoint to receive feedback data from Zendesk. (Source: FDBK-1)
*   FR1.2: The system shall provide a secure REST API endpoint to receive feedback data from Apple App Store and Google Play Store via a configured connector. (Source: FDBK-2)
*   FR1.3: The system shall allow manual entry of feedback items through a web form in the UI. (Source: FDBK-5)
*   FR1.4: All ingested data shall be validated against a predefined schema (including source, customer ID, timestamp, and feedback text) before processing. (Source: FDBK-8)

**FR2: Sentiment Analysis Engine**
*   FR2.1: The system shall automatically analyze the text of all incoming feedback items and assign a sentiment score (Positive, Neutral, Negative). (Source: FDBK-3)
*   FR2.2: The system shall allow an admin to recalibrate the sentiment analysis model by providing corrected sentiment labels. (Source: FDBK-15)

**FR3: Dashboard and Visualization**
*   FR3.1: The system shall display a main dashboard with a high-level overview of sentiment distribution (pie chart), feedback volume over time (line chart), and recent feedback. (Source: FDBK-4)
*   FR3.2: Users shall be able to filter all feedback by date range, sentiment, source, and custom tags. (Source: FDBK-6, FDBK-10)
*   FR3.3: The system shall allow users to create and save custom dashboards with specific visualizations and filters. (Source: FDBK-14)
*   FR3.4: The system shall generate a weekly summary report and email it to subscribed users. (Source: FDBK-11)

**FR4: Feedback Management**
*   FR4.1: Authorized users shall be able to add custom tags (e.g., "UI-Bug", "Feature-Request") to feedback items. (Source: FDBK-10)
*   FR4.2: Users shall be able to mark feedback items as "Reviewed" to track which items have been processed. (Source: FDBK-7)
*   FR4.3: The system shall provide a search function across all feedback text and metadata. (Implied by FDBK-6)

**FR5: User and Access Management**
*   FR5.1: The system shall support user authentication via OAuth 2.0 (Google & Microsoft). (Source: FDBK-9)
*   FR5.2: The system shall implement Role-Based Access Control (RBAC) with three predefined roles: Admin, Product Manager, Support Agent. (Source: FDBK-12)
*   FR5.3: Admins shall have a user management interface to add, remove, and assign roles to users. (Source: FDBK-12)

## 4. Non-Functional Requirements
*   **Performance:** The dashboard shall load initial visualizations in less than 2 seconds. API response times for data ingestion and retrieval shall be under 200ms for the 95th percentile. (Source: FDBK-16)
*   **Security:** All API communications must use HTTPS (TLS 1.2+). User passwords must be hashed (using bcrypt) and salted. PII in feedback must be masked or anonymized where possible. (Source: FDBK-8, FDBK-17)
*   **Scalability:** The system architecture shall be designed to handle a 50% increase in feedback volume over the next 12 months without significant degradation of performance. (Source: FDBK-16)
*   **Usability:** The UI must be intuitive and require less than 30 minutes of training for a new user to perform core functions (view dashboards, filter feedback, tag items). It must comply with WCAG 2.1 Level AA guidelines. (Source: FDBK-13)
*   **Availability:** The system shall achieve 99.5% uptime, excluding scheduled maintenance windows.
*   **Compatibility:** The web portal must be compatible with the latest versions of Chrome, Firefox, Safari, and Edge.

## 5. User Requirements
**Persona 1: Paula, Product Manager**
*   **Needs:** To quickly identify top feature requests and pain points to inform the product roadmap.
*   **User Story:** "As a Product Manager, I want to see a trend chart of frequently mentioned topics so that I can prioritize the backlog based on customer demand." (Source: FDBK-4, FDBK-14)

**Persona 2: Sam, Support Agent**
*   **Needs:** To understand common customer issues to improve support responses and identify knowledge base gaps.
*   **User Story:** "As a Support Agent, I want to filter feedback by 'Negative' sentiment and the 'Bug' tag so that I can quickly identify and escalate critical technical issues." (Source: FDBK-6, FDBK-10)

**Persona 3: Alex, Admin**
*   **Needs:** To ensure system reliability, manage users, and maintain data quality.
*   **User Story:** "As an Admin, I need to configure API keys for new feedback sources and monitor the health of data ingestion pipelines." (Source: FDBK-1, FDBK-12)

## 6. System Requirements
*   **Technology Stack:** Backend: Python (Django/FastAPI), Node.js acceptable. Frontend: React.js or Vue.js. Database: PostgreSQL preferred for relational data integrity. (Source: FDBK-18 Tech Stack discussion)
*   **Integration Requirements:** Must integrate with Zendesk API, Apple App Store Connect API, Google Play Developer API. Must support OAuth 2.0 providers (Google, Microsoft Entra ID). (Source: FDBK-1, FDBK-2, FDBK-9)
*   **Data Requirements:** Must store structured feedback data, user data, tags, and sentiment scores. Must handle semi-structured data from API responses. Estimated initial storage: 50GB, growing at ~5GB/month.
*   **Infrastructure Requirements:** Application shall be deployable on AWS (preferred) or Azure. Use of containerization (Docker) and orchestration (Kubernetes) is required for scalability and maintainability. (Source: FDBK-19)

## 7. Business Rules
*   BR1: A feedback item's initial sentiment is determined automatically by the AI model but can be manually overridden by a user with "PM" or "Admin" role.
*   BR2: Only users with the "Admin" role can add new users to the system or configure new data source integrations.
*   BR3: Feedback items from "App Store" sources are read-only and cannot be edited, only tagged and reviewed. Items from "Manual Entry" can be fully edited by the user who created them.
*   BR4: Weekly reports are automatically generated every Monday at 09:00 AM UTC and sent to all users who have not opted out.

## 8. Assumptions and Dependencies
*   **Assumptions:** The third-party APIs (Zendesk, App Stores) will remain stable and available. Sufficient training data is available to train an accurate initial sentiment model.
*   **Dependencies:** Project timeline is dependent on receiving API credentials and documentation from the Zendesk and app store teams. The performance of the sentiment analysis engine is dependent on the chosen NLP library (e.g., spaCy, Transformers).

## 9. Acceptance Criteria
*   AC1: **Data Ingestion:** 99% of test feedback items sent from a mock Zendesk environment are correctly ingested, parsed, and stored within 5 seconds.
*   AC2: **Sentiment Analysis:** The sentiment engine achieves >85% accuracy against a manually labeled test dataset of 1000 feedback items.
*   AC3: **Dashboard Performance:** The main dashboard loads completely in under 2 seconds with 10,000 feedback items in the database.
*   AC4: **User Access:** A user with "Support Agent" role cannot access the user management or system configuration screens.
*   AC5: **Weekly Report:** A correctly formatted PDF report is generated and emailed to all three test users on the scheduled day and time.

## 10. Glossary
*   **Sentiment Score:** A classification (Positive, Neutral, Negative) assigned to a piece of feedback text.
*   **PII (Personally Identifiable Information):** Any data that can identify an individual (e.g., email, name, phone number).
*   **Data Ingestion Pipeline:** The process and components responsible for receiving, validating, and storing feedback from external sources.
*   **RBAC (Role-Based Access Control):** A method of regulating access to resources based on the roles of individual users.

---

### **Part 2: Design Document Generation Prompt**

You are an expert solutions architect and technical lead. Your task is to create a comprehensive Technical Design Document (TDD) based on the requirements outlined above.

**Project Name:** Customer Feedback and Analytics Portal (Project FDBK)

**1. High-Level System Architecture**
Design and diagram the system architecture. Consider a microservices approach vs. a monolithic approach based on the scalability and integration requirements.
*   Define core services (e.g., API Gateway, Ingestion Service, Analysis Service, Dashboard Service, User Service).
*   Specify how these services will communicate (e.g., REST, message queues like RabbitMQ/Kafka for async processing).
*   Choose a cloud provider (AWS/Azure) and specify the deployment pattern (e.g., using ECS/EKS, or Azure Kubernetes Service).

**2. Component Specifications**
For each core service identified, provide detailed specifications:
*   **Technology Choice:** Justify the choice of programming language and framework (e.g., Ingestion Service in Node.js for high I/O, Analysis Service in Python for ML libraries).
*   **APIs:** Define the key endpoints for each service (e.g., `POST /api/ingest/zendesk`, `GET /api/feedback?sentiment=negative`). Include expected request/response formats (JSON schema).
*   **Data Flow:** Describe how data moves through the system from ingestion to storage to presentation.

**3. Database Design**
*   **Schema Design:** Create a detailed Entity-Relationship Diagram (ERD) for the PostgreSQL database. Key tables: `Users`, `Feedback_Items`, `Tags`, `Sentiment_Analysis`, `Data_Sources`.
*   **Optimization:** Recommend indexing strategies for common query patterns (e.g., filtering by date and sentiment).
*   **Data Retention:** Propose a policy for archiving or purging old feedback data.

**4. API Specifications**
*   Provide a full OpenAPI/Swagger specification for the public-facing API used for data ingestion and the internal API used by the frontend.
*   Detail authentication mechanisms (API keys for ingestion, JWT tokens for frontend communication).

**5. User Interface Design**
*   Provide wireframes or mockups for the key screens: Login, Main Dashboard, Feedback List View, Filter Panel, User Management.
*   Specify the frontend component structure and state management strategy (e.g., using Redux or Context API).

**6. Security Architecture**
*   Detail a defense-in-depth strategy. Include:
    *   Network security (VPC design, security groups).
    *   Application security (input validation, SQL injection prevention, CORS policies).
    *   Data security (encryption at rest and in transit, PII handling).
    *   Authentication and Authorization (OAuth 2.0 flow, JWT token refresh mechanism, RBAC implementation at the API level).

**7. Deployment Architecture**
*   Diagram the CI/CD pipeline (e.g., using GitHub Actions/GitLab CI).
*   Specify infrastructure as code tools (e.g., Terraform, CloudFormation).
*   Describe the containerization strategy (Dockerfile examples for each service).
*   Outline monitoring and logging solutions (e.g., Prometheus/Grafana for metrics, ELK Stack for logs).

**8. Testing Strategy**
*   Define testing pyramids for each service: Unit, Integration, End-to-End.
*   Specify how the sentiment analysis model's accuracy will be continuously tested and monitored.
*   Plan for load testing the ingestion API and dashboard to meet performance NFRs.

**Output Format:**
Generate a formal Technical Design Document with sections for each of the points above. Use clear diagrams (you can describe them for now) and professional, precise language. Justify all key technical decisions.