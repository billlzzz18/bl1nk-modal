# Project Workflow (Standard Edition)

## Core Principles
1. **Plan Mode First:** ทุกลำดับการทำงานต้องเริ่มจากการวางแผนใน `plan.md` ของแต่ละ Track
2. **Standardized Tech Stack:** การเปลี่ยนแปลง Tech Stack ต้องระบุใน `tech-stack.md` ก่อนเริ่ม Implementation
3. **Hybrid TDD (Python + Rust):** เขียน Test ก่อน Implement เสมอ สำหรับทั้งฝั่ง Python และ Rust
4. **Code Guidelines Compliance:** โค้ดที่เขียนต้องผ่านการตรวจสอบตาม `code_styleguides/`
5. **Phase-Gate Verification:** ทุกครั้งที่จบ Phase ต้องมีการทำ Checkpoint และ Verification เสมอ

## Development Lifecycle

### 1. Task Management
- เลือกงานจาก `plan.md` ตามลำดับ
- เปลี่ยนสถานะจาก `[ ]` (Pending) เป็น `[~]` (In Progress)
- เมื่อจบงาน เปลี่ยนเป็น `[x]` พร้อมระบุ 7-char Commit SHA

### 2. Implementation Cycle (TDD)

#### สำหรับ Python (FastAPI/Modal)
1. **Red Phase:** สร้างไฟล์ใน `tests/` และเขียน `pytest` ให้รันแล้ว Fail
2. **Green Phase:** เขียน Python โค้ดใน `app/` ให้ Test ผ่าน
3. **Refactor Phase:** ปรับปรุงโค้ดให้สะอาด (Clean Code) และรัน Test อีกรอบ

#### สำหรับ Rust Engine (PyO3)
1. **Red Phase:** เขียน unit test ในไฟล์ `.rs` (ภายใต้โมดูล `tests`) หรือ `tests/` โฟลเดอร์ ให้ `cargo test` แล้ว Fail
2. **Green Phase:** เขียน Rust โค้ดให้ Test ผ่าน
3. **PyO3 Integration:** รัน `maturin develop` เพื่อ build และติดตั้ง module เข้ากับ Python environment
4. **Integration Test:** เขียน Python test เพื่อเรียกใช้งาน Rust module และยืนยันผลลัพธ์ผ่าน Python interface

### 3. Quality & Security Gates
- **Rust Clippy:** รัน `cargo clippy` เพื่อตรวจสอบ Linting ใน Rust
- **Python Ruff/Flake8:** รัน Linter ตรวจสอบโค้ด Python
- **Type Checking:** ใช้ `pyright` หรือ `mypy` สำหรับ Python type hints
- **Security Check:** รัน `cargo audit` (Rust) และ `safety` (Python) เมื่อมีการเพิ่ม dependency ใหม่

## Phase Checkpointing Protocol
ทุกครั้งที่จบ Phase ใน `plan.md` ให้ทำตามขั้นตอนดังนี้:
1. **Automated Verification:** รัน `pytest` และ `cargo test` ทั้งหมด
2. **Coverage Audit:** ตรวจสอบ Code Coverage (เป้าหมาย >80%)
3. **Manual Verification:** ทำตามขั้นตอนที่ระบุใน Task `Conductor - User Manual Verification`
4. **Git Checkpoint:** สร้าง commit checkpoint และแนบ Git Notes สรุปสิ่งที่ทำเสร็จ

## Code Review Process (Self-Audit)
ก่อนส่งงานหรือรวมโค้ด (PR) ให้ตรวจสอบ:
- [ ] ฟังก์ชัน Public มี Docstrings (Python) และ RustDoc (Rust)
- [ ] ไม่มี Hardcoded Secrets หรือ API Keys
- [ ] จัดการ Error อย่างเหมาะสม (ไม่มี unwrap/panic ใน Rust, มี Exception Handling ใน Python)
- [ ] รองรับ Mobile Responsive (ถ้าเป็น UI)
- [ ] โค้ดผ่าน Linter และ Type Checker ทั้งคู่

## Emergency Procedures
- **Rust Compile Error:** ตรวจสอบ Ownership/Borrowing rules (อ่าน `rust-best-practices` skill)
- **Modal Deployment Fail:** ตรวจสอบ Environment Variables และ Modal Secrets
- **Data Integrity Issue:** ตรวจสอบ SQLite Schema Migration
