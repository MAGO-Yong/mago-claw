# Postquantum Cryptography — Research Report

**Year:** 2025 (announced October 21, 2024)
**Topic Code:** 2025-04
**Research Date:** 2026-03-22

---

## Round 1: Foundational Research Memo

### 1. Topic Alignment

**Definition (Gartner):** Postquantum cryptography (PQC) refers to cryptographic algorithms resistant to attacks from quantum computers. Today's widely-used public key cryptography (RSA, ECC) is mathematically vulnerable to quantum computing attacks—a sufficiently powerful quantum computer could break these algorithms in practical timeframes. PQC replaces these vulnerable algorithms with ones that remain secure even against quantum attacks.

**The Threat:**
Modern encryption (RSA-2048, ECC-256) relies on mathematical problems that are hard for classical computers (integer factorization, elliptic curve discrete logarithm). Quantum computers using Shor's algorithm could solve these problems exponentially faster, breaking current encryption.

**"Harvest Now, Decrypt Later" Attack:**
Nation-state adversaries are likely collecting encrypted data TODAY to decrypt LATER when quantum computers are available. This means:
- Data encrypted today with RSA is vulnerable to future quantum decryption
- Sensitive data with long secrecy requirements (government secrets, medical records, IP) is at risk NOW
- Organizations must start migrating TODAY to protect future data security

**Types of Quantum-Resistant Algorithms:**
1. **Lattice-based cryptography**: Based on hard lattice problems; fastest PQC option; CRYSTALS-Kyber (now ML-KEM), CRYSTALS-Dilithium (now ML-DSA)
2. **Hash-based signatures**: Based on cryptographic hash functions; SPHINCS+ (now SLH-DSA)
3. **Code-based cryptography**: Based on error-correcting codes; BIKE, Classic McEliece
4. **Isogeny-based cryptography**: Based on elliptic curve isogenies; most compact but computationally slow

**Adjacent Concepts:**
- **Confidential Computing** (2022, 2026): Secures data in use; PQC secures data in transit/storage
- **Privacy-Enhancing Computation** (2021, 2022): PQC is a component of broader PEC
- **Zero Trust** / **Cybersecurity Mesh**: Security architecture that must incorporate PQC
- **AI Security Platforms** (2026): Adjacent in protecting against emerging threats

---

### 2. Context and Drivers

**NIST PQC Standardization (August 2024):**

The most critical milestone: NIST finalized three PQC standards in August 2024:
- **FIPS 203** (ML-KEM / CRYSTALS-Kyber): Key encapsulation mechanism; primary encryption replacement
- **FIPS 204** (ML-DSA / CRYSTALS-Dilithium): Digital signatures
- **FIPS 205** (SLH-DSA / SPHINCS+): Digital signatures (hash-based, alternative)

A fourth algorithm (BIKE or Classic McEliece) expected to be standardized separately for additional options.

**US Government Mandate:**
- National Security Memorandum 10 (2022): Required federal agencies to prioritize PQC migration
- CISA "Quantum-Readiness" toolkit: Published for enterprise guidance
- NSA: All national security systems must use PQC by 2030

**Quantum Computing Timeline:**
The key question for enterprises: when will quantum computers be capable enough to break RSA-2048?

- Most expert estimates: 10-20 years to a "cryptographically relevant quantum computer" (CRQC)
- Pessimistic estimates: 5-10 years (nation-state programs with classified capabilities)
- IBM Quantum roadmap: 100,000 qubit system by 2033 (may not be sufficient for Shor's algorithm at RSA scale)

**The harvest-now-decrypt-later threat means: don't wait for quantum computers to be ready. Start now.**

---

### 3. Foundational Research Findings

#### 3.1 Migration Complexity

PQC migration is more complex than typical software updates because cryptography is embedded everywhere:
- TLS (HTTPS) connections
- Digital signatures on code, documents, certificates
- VPN tunnels
- SSH connections
- Email (S/MIME, PGP)
- PKI certificates
- IoT device firmware signing
- Long-lived data encryption

**Key characteristics of ML-KEM (Kyber) vs. RSA:**
- Public key size: 1,184 bytes (ML-KEM-768) vs. 256 bytes (RSA-2048)—4.6x larger
- Ciphertext size: 1,088 bytes vs. 256 bytes—4.25x larger
- Performance: Faster than RSA in many operations
- Network impact: Larger key/cert sizes affect TLS handshake size

For most web applications, the size increase is manageable. For constrained IoT devices with limited memory/bandwidth, migration is more challenging.

#### 3.2 Industry Progress

**Cloud Providers:**
- **AWS**: KMS supports ML-KEM for TLS; post-quantum TLS in AWS services
- **Google**: Post-quantum TLS deployed on Google servers and Chrome (CECPQ2)
- **Cloudflare**: Post-quantum TLS available for all customers; NTRU/ML-KEM hybrid

**Hardware Security Modules:**
- **Thales**: HSMs supporting PQC algorithms
- **Entrust**: nShield HSMs with PQC support
- **IBM**: PQC algorithms on IBM Z mainframes and crypto cards

**Browser Support:**
- Chrome: ML-KEM (Kyber) support in TLS 1.3 (2024)
- Firefox: Post-quantum key agreement in TLS
- Safari: In development

**Software Libraries:**
- **Open Quantum Safe (OQS)**: Open-source PQC implementation library; liboqs
- **Bouncy Castle**: Popular Java crypto library with PQC support
- **OpenSSL**: PQC support in development (available via provider interface)

#### 3.3 Enterprise Cryptographic Inventory

The critical first step: **cryptographic discovery**.

Before migrating, enterprises need to know:
- Where is cryptography used? (Applications, services, protocols, APIs)
- What algorithms are in use? (RSA-2048? ECC P-256? AES-256?)
- Where is data encrypted at rest? (Databases, storage, backups)
- What certificates exist and when do they expire?
- What systems have long-lived encrypted data that needs protection?

Tools for cryptographic discovery:
- **IBM Cryptographic Bill of Materials (CBOM)**: Inventory format for cryptographic assets
- **Keyfactor**: Certificate management and crypto inventory
- **Venafi**: Machine identity management including crypto discovery
- **DigiCert**: Certificate discovery and management

#### 3.4 Hybrid Approaches (Recommended by NIST)

During transition, NIST recommends hybrid approaches:
- Use BOTH classical (RSA/ECC) AND post-quantum algorithms
- If either is broken, the other provides security
- Allows gradual transition without complete dependence on new PQC algorithms (which are new and less battle-tested)

**X25519Kyber768**: Hybrid key agreement combining X25519 (classical) and ML-KEM-768 (post-quantum). Being standardized as the recommended near-term approach for TLS.

---

### 4. Maturity Assessment

| Component | Maturity | Note |
|-----------|----------|------|
| PQC standards (FIPS 203-205) | Finalized | Available for implementation |
| Software libraries | Medium-High | OQS, Bouncy Castle available |
| TLS/HTTPS | Medium | Cloud and browsers supporting; servers lagging |
| PKI/Certificates | Low-Medium | CAs beginning PQC cert support |
| IoT migration | Low | Constrained devices need new firmware/hardware |
| Enterprise applications | Low | Most enterprise software not yet PQC-migrated |

---

## Round 2: Deep-Dive — Enterprise PQC Migration Roadmap

### Research Question

**Most practical question:** For a typical enterprise, what is the realistic PQC migration roadmap given the 2024 standards finalization?

### Deep Findings

#### Migration Priority Framework

Not all cryptographic use requires immediate migration. Priority is determined by:
- **Data sensitivity × Data lifetime**: High-sensitivity data with long secrecy requirements (30+ years) → highest priority
- **Exposure to harvest-now-decrypt-later**: Internet-facing TLS connections → highest exposure
- **Regulatory requirements**: Government/defense contractors → mandate by 2030

**Priority Tier 1 (Act Now):**
- Internet-facing TLS connections for sensitive data (financial transactions, medical records, legal communications)
- Key exchange for long-term secrets (encryption keys that will be used for years)
- Data that must remain secret for 20+ years

**Priority Tier 2 (Plan for 2025-2027):**
- Internal network communications
- Code signing certificates
- Document digital signatures
- Email encryption

**Priority Tier 3 (Monitor for 2028-2030):**
- Short-lived data encryption
- Authentication tokens with short lifetimes
- IoT devices (plan for hardware replacement cycle)

#### Practical 5-Step Enterprise Roadmap

**Step 1 (2024-2025): Cryptographic Inventory**
Identify all cryptographic dependencies using CBOM approach. Understand what algorithms are used where.

**Step 2 (2025-2026): Risk Assessment**
For each cryptographic use:
- Data sensitivity (what's the consequence of breach?)
- Data lifetime (how long must it remain secret?)
- Exposure (is this internet-accessible?)
- Harvest vulnerability (is anyone likely collecting this data now?)

**Step 3 (2025-2026): Standards Alignment**
Adopt NIST FIPS 203 (ML-KEM) as the key encapsulation standard. Plan certificate and key management infrastructure updates.

**Step 4 (2026-2028): Tier 1 Migration**
Migrate highest-priority systems to hybrid classical + PQC approaches. Use vendor-provided upgrades where available (cloud providers, browsers, CDNs already migrating).

**Step 5 (2028-2030): Full Migration**
Complete migration across all tiers, including legacy systems and IoT devices.

**Most organizations need to start Step 1 now.** The 2030 deadline for government contractors gives the industry timeline. Commercial enterprises should plan to be complete by 2030 for high-sensitivity data.

### Round 2 Conclusion

Postquantum cryptography is not optional—it's a pre-planned, mandatory migration with a ~2030 horizon for most sensitive data. The NIST standards finalization in August 2024 removed the "waiting for standards" excuse. Enterprises should start with cryptographic inventory (know what you have), assess harvest-now-decrypt-later risk, and begin migrating highest-priority internet-facing systems first using hybrid approaches. The migration will take 5-7 years for most large enterprises; those who haven't started by 2025-2026 will face a crunch by 2030.

---

## Sources

1. Gartner 2025 Strategic Technology Trends
2. NIST FIPS 203, 204, 205 publications (August 2024)
3. National Security Memorandum 10 on quantum computing (2022)
4. IBM Quantum roadmap publications
5. Open Quantum Safe project (openquantumsafe.org)
6. Google and AWS post-quantum TLS announcements
7. CISA Quantum-Readiness toolkit
8. Cloudflare: "The post-quantum future is now" blog post (2024)

---

*Report Status: Complete — Round 1 + Round 2*
*Word Count: ~1,150 words*
