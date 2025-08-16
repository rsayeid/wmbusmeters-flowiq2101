# FlowIQ2101 Meter Management Architecture Documentation
## Comprehensive System Design for 10,000+ Meters Across Multiple Societies

**Version**: 1.0  
**Date**: August 16, 2025  
**Project**: wmbusmeters-flowiq2101  
**Scope**: Production-scale meter management system

---

## 🏗️ **System Overview**

### **Current Scale & Requirements**
- **Meters**: 10,000+ FlowIQ2101 meters (expanding)
- **Societies**: 2 currently, with continuous growth
- **Data Collection Methods**:
  - Manual: VW1811 handheld + Android app (1-2x monthly)
  - Automated: Gateways continuously capturing + cloud endpoints
- **Priority**: Enable manual capturing with advanced Android app
- **Integration**: Seamless connection with meter-management-analysis system

### **Business Objectives**
1. Replace third-party decryption solutions
2. Enable rapid Android app development
3. Support multiple data export formats (Excel, S3, etc.)
4. Provide flexible meter scanning strategies
5. Real-time progress tracking
6. Future-proof integration capabilities

---

## 🎯 **Recommended Architecture: Serverless wMBus Decryption Service**

### **Core AWS Architecture**

```yaml
┌─────────────────────────────────────────────────────────────────┐
│                    FlowIQ2101 Meter Management System          │
└─────────────────────────────────────────────────────────────────┘

┌─ Android App (VW1811) ──┐    ┌─ Continuous Gateways ──┐
│ • Live meter tracking   │    │ • 24/7 data capture    │
│ • Multi-scan modes      │    │ • Auto data forwarding │
│ • Excel/S3 export       │    │ • Batch processing     │
│ • Real-time progress    │    │ • Cloud integration    │
└─────────┬───────────────┘    └──────┬──────────────────┘
          │                           │
          │    ┌─ Meter Management ────┤
          │    │ Analysis System       │
          │    │ (Existing Amplify)    │
          │    └───────┬───────────────┘
          │            │
          └─────────┬──┴───────────────────┐
                    │                      │
            ┌───────▼────────┐    ┌────────▼─────────┐
            │  API Gateway   │    │   Authentication  │
            │ (Multi-tenant) │◄───┤   (Cognito)      │
            │ Regional       │    │   Shared Pool     │
            └───────┬────────┘    └──────────────────┘
                    │
        ┌───────────▼────────────┐
        │   Lambda Functions     │
        │ ┌─ Telegram Processor ─┤ ← vw1871_frame_extractor.py
        │ ├─ Batch Processor    ─┤ ← wmbusmeters integration
        │ ├─ Export Generator   ─┤ ← Excel/S3 exports
        │ ├─ Progress Tracker   ─┤ ← Real-time updates
        │ └─ Config Manager     ─┤ ← Meter/society mgmt
        └───────────┬────────────┘
                    │
    ┌───────────────┼─────────────────────┐
    │               │                     │
┌───▼────┐    ┌────▼─────┐    ┌─────▼──────────┐
│DynamoDB│    │    S3    │    │ EventBridge/SQS│
│Tables: │    │Buckets:  │    │ Real-time Msgs │
│• Meters│    │• Exports │    │ Progress Events│
│• Scans │    │• Backups │    │ Notifications  │
│• Config│    │• Archives│    │ Workflows      │
└────────┘    └──────────┘    └────────────────┘
```

---

## 📱 **Android App Requirements & Technology Stack**

### **Advanced App Features**
```yaml
Core Functionality:
  - VW1811 Bluetooth integration
  - Multiple scanning modes:
    • Single flat (multiple meters)
    • Single tower (all flats)
    • Multiple towers 
    • Society-wide free roam
  - Real-time progress tracking
  - Live meter status visualization
  - Multi-format exports (Excel, S3, JSON)
  
Navigation & UX:
  - Interactive society/tower/flat maps
  - Progress indicators and completion status
  - Offline capability with sync
  - Barcode/QR code meter identification
  - Voice guidance for meter locations
```

### **🚀 Recommended Technology: AWS Amplify Gen 2 + Native Android**

**Why This Combination is Perfect:**

1. **Rapid Development**:
   - AWS Amplify Gen 2 provides instant backend
   - TypeScript support for type safety
   - Auto-generated GraphQL APIs
   - Real-time subscriptions out-of-the-box

2. **Seamless Integration**:
   - Shares infrastructure with meter-management-analysis
   - Common authentication (Cognito)
   - Unified data models
   - No integration complexity

3. **Native Android Performance**:
   - Direct Bluetooth access for VW1811
   - Optimal performance for scanning operations
   - Native file system access for exports
   - Superior offline capabilities

### **Technology Stack Details**

```yaml
Frontend (Android):
  Framework: Native Android (Kotlin)
  Architecture: MVVM + Repository Pattern
  Database: Room (offline-first)
  Networking: Amplify Android SDK
  Bluetooth: Android Bluetooth APIs
  
Backend (AWS Amplify Gen 2):
  Infrastructure: CDK + TypeScript
  API: GraphQL + REST endpoints
  Authentication: Cognito User Pools
  Database: DynamoDB
  Storage: S3
  Functions: Lambda
  Real-time: AppSync Subscriptions
  
Additional Services:
  Exports: Lambda + S3 pre-signed URLs
  Progress: EventBridge + WebSocket
  Maps: MapBox/Google Maps integration
  Analytics: CloudWatch + X-Ray
```

---

## 🗄️ **Data Architecture**

### **DynamoDB Schema Design**

```yaml
# Primary Tables
MeterConfigurations:
  PK: societyId
  SK: meterId
  Attributes:
    - flatNumber
    - towerName
    - meterType: "FlowIQ2101"
    - encryptionKey
    - serialNumber
    - installationDate
    - location: { lat, lng }
    - status: "active|inactive|maintenance"

ScanSessions:
  PK: societyId#scanId
  SK: timestamp
  Attributes:
    - userId
    - scanMode: "flat|tower|society|free"
    - targetList: [meterIds]
    - progress: { completed, total, percentage }
    - status: "active|completed|failed"
    - exportFormats: ["excel", "s3", "json"]

MeterReadings:
  PK: societyId#meterId
  SK: timestamp
  Attributes:
    - scanSessionId
    - consumption
    - rawTelegram
    - decryptedData
    - readingQuality: "good|fair|poor"
    - gpsLocation: { lat, lng }

SocietyStructure:
  PK: societyId
  SK: tower#towerName OR flat#flatNumber
  Attributes:
    - parentId (for hierarchical structure)
    - meterIds: [array of meter IDs]
    - coordinates: { lat, lng }
    - residents: { name, contact }
```

### **S3 Bucket Organization**

```yaml
Bucket Structure:
s3://flowiq-meter-data/
├── societies/
│   ├── {societyId}/
│   │   ├── exports/
│   │   │   ├── excel/{scanSessionId}.xlsx
│   │   │   ├── json/{scanSessionId}.json
│   │   │   └── archives/{year}/{month}/
│   │   ├── configurations/
│   │   │   ├── meters.json
│   │   │   └── society-structure.json
│   │   └── backups/
│   │       └── daily-snapshots/
├── temp-uploads/
│   └── {userId}/{sessionId}/
└── templates/
    ├── excel-templates/
    └── report-templates/
```

---

## 📊 **API Design**

### **GraphQL Schema (Amplify Gen 2)**

```graphql
type Society @model @auth(rules: [
  { allow: groups, groups: ["SuperAdmin"] },
  { allow: groups, groups: ["SocietyAdmin"], operations: [read, update] }
]) {
  id: ID!
  name: String!
  address: String!
  meters: [Meter] @hasMany
  scanSessions: [ScanSession] @hasMany
  structure: AWSJSON # Towers, flats hierarchy
}

type Meter @model @auth(rules: [
  { allow: groups, groups: ["SuperAdmin", "SocietyAdmin"] }
]) {
  id: ID!
  societyId: ID! @index(name: "bySociety")
  serialNumber: String!
  flatNumber: String!
  towerName: String!
  encryptionKey: String!
  location: Location
  readings: [Reading] @hasMany
  status: MeterStatus!
}

type ScanSession @model @auth(rules: [
  { allow: owner },
  { allow: groups, groups: ["SocietyAdmin"], operations: [read] }
]) {
  id: ID!
  societyId: ID!
  userId: ID!
  mode: ScanMode!
  targetMeters: [String!]!
  progress: Progress!
  status: SessionStatus!
  readings: [Reading] @hasMany
  exports: [Export] @hasMany
}

type Reading @model {
  id: ID!
  meterId: ID!
  sessionId: ID!
  consumption: Float!
  timestamp: AWSDateTime!
  rawTelegram: String!
  decryptedData: AWSJSON!
  quality: ReadingQuality!
  gpsLocation: Location
}

# Custom types
type Location {
  lat: Float!
  lng: Float!
}

type Progress {
  completed: Int!
  total: Int!
  percentage: Float!
}

enum ScanMode {
  FLAT
  TOWER
  SOCIETY
  FREE_ROAM
}

enum MeterStatus {
  ACTIVE
  INACTIVE
  MAINTENANCE
}

enum SessionStatus {
  ACTIVE
  COMPLETED
  FAILED
  PAUSED
}

enum ReadingQuality {
  GOOD
  FAIR
  POOR
}
```

### **REST API Endpoints (Lambda Functions)**

```yaml
Decryption Service:
  POST /api/decrypt/telegram
    Body: { telegram, meterId, sessionId }
    Response: { success, consumption, timestamp, quality }

  POST /api/decrypt/batch
    Body: { telegrams: [{ telegram, meterId }], sessionId }
    Response: { results: [readings], summary }

Export Service:
  POST /api/export/excel
    Body: { sessionId, format, template }
    Response: { downloadUrl, expiresAt }

  POST /api/export/s3
    Body: { sessionId, bucketPath }
    Response: { success, s3Location }

Progress Service:
  GET /api/sessions/{sessionId}/progress
    Response: { completed, total, percentage, remaining }

  POST /api/sessions/{sessionId}/update
    Body: { meterId, status, reading }
    Response: { success, updatedProgress }

Configuration Service:
  GET /api/societies/{societyId}/meters
    Query: ?tower=ABC&flat=101
    Response: { meters: [meter configs] }

  GET /api/societies/{societyId}/structure
    Response: { towers, flats, meterMapping }
```

---

## 🎯 **Android App Scanning Modes**

### **1. Single Flat Mode**
```kotlin
data class FlatScanMode(
    val flatNumber: String,
    val expectedMeters: List<Meter>,
    val progressTracker: ScanProgress
) {
    fun getNextMeter(): Meter?
    fun markMeterComplete(meterId: String)
    fun getRemainingMeters(): List<Meter>
}
```

### **2. Tower Mode**
```kotlin
data class TowerScanMode(
    val towerName: String,
    val flats: List<Flat>,
    val totalMeters: Int,
    val currentFlat: Flat?,
    val progressByFlat: Map<String, ScanProgress>
) {
    fun getNextFlat(): Flat?
    fun getCurrentFlatMeters(): List<Meter>
    fun getTowerProgress(): OverallProgress
}
```

### **3. Society-Wide Mode**
```kotlin
data class SocietyScanMode(
    val towers: List<Tower>,
    val scanStrategy: ScanStrategy,
    val currentLocation: Tower?,
    val overallProgress: SocietyProgress
) {
    fun optimizeRoute(): List<ScanLocation>
    fun getNextOptimalLocation(): ScanLocation?
    fun updateProgress(reading: Reading)
}
```

### **4. Free Roam Mode**
```kotlin
data class FreeRoamMode(
    val availableMeters: List<Meter>,
    val scannedMeters: Set<String>,
    val gpsTracking: Boolean
) {
    fun identifyNearbyMeters(location: Location): List<Meter>
    fun addOpportunisticReading(reading: Reading)
    fun suggestNextLocation(): Location?
}
```

---

## 📈 **Real-time Progress Tracking**

### **Live Updates Architecture**
```yaml
Progress Flow:
  Android App → GraphQL Mutation → AppSync → Lambda → DynamoDB
                     ↓
  AppSync Subscription → Real-time UI Updates
                     ↓
  WebSocket/EventBridge → Dashboard Notifications
```

### **Progress UI Components**
```kotlin
@Composable
fun ScanProgressScreen(
    scanSession: ScanSession,
    onMeterScanned: (Reading) -> Unit
) {
    Column {
        // Overall progress
        LinearProgressIndicator(
            progress = scanSession.progress.percentage
        )
        
        // Live meter status grid
        LazyVerticalGrid {
            items(scanSession.targetMeters) { meter ->
                MeterStatusCard(
                    meter = meter,
                    status = getMeterStatus(meter.id),
                    onClick = { navigateToMeter(meter) }
                )
            }
        }
        
        // Real-time statistics
        ProgressStats(
            completed = scanSession.progress.completed,
            total = scanSession.progress.total,
            timeElapsed = getElapsedTime(),
            estimatedRemaining = getEstimatedTime()
        )
    }
}
```

---

## 📤 **Export System Design**

### **Multi-format Export Architecture**

```yaml
Export Pipeline:
  User Request → Lambda Function → Data Processing → Format Generation → S3 Upload → Notification

Supported Formats:
  Excel:
    - Multiple worksheets (summary, detailed readings, meter configs)
    - Charts and graphs
    - Conditional formatting
    - Password protection option
    
  S3:
    - JSON format for API consumption
    - CSV for data analysis
    - Compressed archives for bulk data
    - Metadata tagging
    
  Real-time:
    - WebSocket streaming for live dashboards
    - GraphQL subscriptions for app updates
    - Email notifications for completion
```

### **Excel Export Features**
```typescript
interface ExcelExportConfig {
  template: 'standard' | 'detailed' | 'summary';
  includeCharts: boolean;
  includeMetadata: boolean;
  passwordProtect: boolean;
  worksheets: {
    summary: SummaryConfig;
    readings: ReadingsConfig;
    meters: MeterConfig;
    analytics: AnalyticsConfig;
  };
}

// Lambda function for Excel generation
export const generateExcelExport = async (
  sessionId: string, 
  config: ExcelExportConfig
): Promise<ExportResult> => {
  const data = await fetchSessionData(sessionId);
  const workbook = new ExcelJS.Workbook();
  
  // Generate worksheets based on config
  await addSummaryWorksheet(workbook, data, config.worksheets.summary);
  await addReadingsWorksheet(workbook, data, config.worksheets.readings);
  await addMetersWorksheet(workbook, data, config.worksheets.meters);
  
  if (config.includeCharts) {
    await addChartsWorksheet(workbook, data);
  }
  
  const buffer = await workbook.xlsx.writeBuffer();
  const s3Key = await uploadToS3(buffer, sessionId);
  
  return {
    downloadUrl: await generatePresignedUrl(s3Key),
    size: buffer.length,
    expiresAt: Date.now() + (24 * 60 * 60 * 1000) // 24 hours
  };
};
```

---

## 💰 **Cost Analysis & Optimization**

### **Estimated Monthly Costs (10K Meters, 2 Readings/Month)**

```yaml
Core Services:
  Lambda Functions:     $8-12   # Telegram processing + exports
  API Gateway:          $4-8    # 20K API calls + data transfer
  DynamoDB:            $3-6    # On-demand pricing
  S3 Storage:          $2-4    # Exports + backups
  AppSync:             $3-5    # GraphQL + subscriptions
  Cognito:             $1-2    # User authentication
  CloudWatch:          $2-3    # Monitoring + logs
  
Additional Features:
  EventBridge:         $1-2    # Real-time events
  SES (emails):        $0-1    # Export notifications
  Data Transfer:       $1-3    # API responses + file downloads
  
Total Monthly:       $25-46   # Extremely cost-effective!
Annual Cost:         $300-550 # Much cheaper than third-party solutions

Cost per Meter:      $0.003-0.005/month per meter
Cost per Reading:    $0.0015-0.002 per reading
```

### **Cost Optimization Strategies**
```yaml
Immediate Optimizations:
  - Use Lambda ARM processors (20% cheaper)
  - DynamoDB on-demand vs provisioned
  - S3 Intelligent Tiering
  - CloudWatch log retention policies
  - Regional API Gateway (vs Edge)

Long-term Optimizations:
  - Reserved capacity for predictable workloads
  - Custom Lambda layers for faster cold starts
  - Compression for data transfer
  - Caching strategies (ElastiCache when needed)
  - Archival policies for old data
```

---

## 🚀 **Development Timeline & Milestones**

### **Phase 1: Foundation (Weeks 1-2)**
```yaml
Week 1:
  ✓ Setup AWS Amplify Gen 2 project
  ✓ Design DynamoDB schema
  ✓ Create core Lambda functions
  ✓ Package wmbusmeters for Lambda layer
  ✓ Setup API Gateway endpoints

Week 2:
  ✓ Implement authentication integration
  ✓ Create basic GraphQL schema
  ✓ Setup S3 buckets and policies
  ✓ Test telegram decryption pipeline
  ✓ Create development environment
```

### **Phase 2: Android App Core (Weeks 3-4)**
```yaml
Week 3:
  ✓ Android project setup with Amplify SDK
  ✓ Bluetooth integration for VW1811
  ✓ Basic UI with navigation
  ✓ Authentication screens
  ✓ Society/meter data loading

Week 4:
  ✓ Implement scanning modes (flat, tower, society)
  ✓ Real-time progress tracking
  ✓ Offline capability with Room database
  ✓ Basic export functionality
  ✓ Testing with sample data
```

### **Phase 3: Advanced Features (Weeks 5-6)**
```yaml
Week 5:
  ✓ Excel export with templates
  ✓ S3 integration for cloud exports
  ✓ GPS integration for location tracking
  ✓ Barcode/QR scanning for meter identification
  ✓ Voice guidance system

Week 6:
  ✓ Performance optimization
  ✓ Error handling and retry logic
  ✓ Advanced UI/UX improvements
  ✓ Comprehensive testing
  ✓ Documentation and training materials
```

### **Phase 4: Integration & Deployment (Weeks 7-8)**
```yaml
Week 7:
  ✓ Integration with meter-management-analysis
  ✓ Production environment setup
  ✓ Security audit and penetration testing
  ✓ Performance testing with load simulation
  ✓ Beta testing with select users

Week 8:
  ✓ Production deployment
  ✓ User training and documentation
  ✓ Monitoring and alerting setup
  ✓ Support processes
  ✓ Launch and initial feedback collection
```

---

## 🔐 **Security & Compliance**

### **Data Protection**
```yaml
Encryption:
  - At Rest: DynamoDB + S3 encryption
  - In Transit: TLS 1.3 for all communications
  - Application: AES-256 for sensitive data
  - Keys: AWS KMS managed keys

Access Control:
  - Cognito User Pools with MFA
  - IAM roles with least privilege
  - VPC endpoints for internal communication
  - API rate limiting and throttling

Compliance:
  - Data residency requirements
  - GDPR compliance for personal data
  - Audit logging for all operations
  - Data retention policies
  - Backup and disaster recovery
```

### **Monitoring & Alerting**
```yaml
CloudWatch Metrics:
  - API Gateway performance
  - Lambda function duration and errors
  - DynamoDB throttling and capacity
  - Custom business metrics

X-Ray Tracing:
  - End-to-end request tracing
  - Performance bottleneck identification
  - Error root cause analysis

Custom Alerts:
  - High error rates
  - Performance degradation
  - Cost anomalies
  - Security events
```

---

## 🌟 **Future Enhancements**

### **Advanced Analytics**
```yaml
AI/ML Integration:
  - Consumption pattern analysis
  - Anomaly detection for meter readings
  - Predictive maintenance alerts
  - Route optimization for scanning

Enhanced Mobile Features:
  - Augmented Reality for meter identification
  - Voice commands for hands-free operation
  - Integration with smart watches
  - Advanced mapping and navigation
```

### **Scalability Improvements**
```yaml
Performance:
  - GraphQL caching with AppSync
  - Lambda provisioned concurrency
  - DynamoDB global tables for multi-region
  - CDN for static assets

Operations:
  - Automated deployments with CI/CD
  - Infrastructure as Code (CDK)
  - Automated testing pipelines
  - Disaster recovery procedures
```

---

## 📞 **Support & Maintenance**

### **Operational Excellence**
```yaml
24/7 Monitoring:
  - CloudWatch dashboards
  - Automated alerting
  - Performance metrics
  - Cost optimization alerts

Support Processes:
  - Tiered support system
  - Knowledge base and documentation
  - User training programs
  - Regular system health checks

Continuous Improvement:
  - Monthly performance reviews
  - User feedback integration
  - Feature enhancement pipeline
  - Technology stack updates
```

---

**Document Status**: Complete  
**Next Review**: Monthly  
**Owner**: FlowIQ2101 Development Team  
**Stakeholders**: Android Development, Backend Team, DevOps, Product Management  

---

*This document serves as the authoritative reference for the FlowIQ2101 meter management system architecture and implementation strategy.*
