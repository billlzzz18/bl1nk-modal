# Rust Code Style Guide (Extended)

## 1. General Principles
- **Safety First:** หลีกเลี่ยงการใช้ `unsafe` block ยกเว้นกรณีที่จำเป็นจริงๆ สำหรับ PyO3 FFI และต้องมีการตรวจสอบอย่างเข้มงวด
- **Idiomatic Rust:** ใช้คำสั่งที่ตรงตามมาตรฐาน Rust (e.g., use `match` instead of heavy `if-else`, use `Iterators`)
- **Ownership & Borrowing:** ทำความเข้าใจเรื่อง ownership อย่างดีเพื่อลดการ `.clone()` โดยไม่จำเป็น

## 2. Naming Conventions
- **Files/Modules:** `snake_case.rs`
- **Structs/Enums/Traits:** `PascalCase`
- **Functions/Variables/Methods:** `snake_case`
- **Constants/Statics:** `SCREAMING_SNAKE_CASE`

## 3. Error Handling (PyO3 Integration)
- **No Panics:** ห้ามใช้ `unwrap()` หรือ `expect()` ใน Production code ให้ใช้ `Result<T, E>` และ `Option<T>` เสมอ
- **Result Mapping:** ฟังก์ชันที่ export ไป Python ต้องคืนค่าเป็น `PyResult<T>`
- **Custom Exceptions:** ใช้ `create_exception!` สำหรับนิยาม Error ที่เฉพาะเจาะจงของโปรเจกต์
- **Automatic Conversion:** Implement `From<MyError> for PyErr` เพื่อให้ Rust `?` operator ทำงานร่วมกับ Python exception ได้โดยอัตโนมัติ

```rust
// ตัวอย่างการทำ Error Mapping
impl From<EngineError> for PyErr {
    fn from(err: EngineError) -> PyErr {
        PyValueError::new_err(err.to_string())
    }
}
```

## 4. Performance & Concurrency
- **GIL Management:** สำหรับฟังก์ชันที่ใช้ CPU หนัก (Heavy Computation) ให้ใช้ `py.allow_threads(|| { ... })` เพื่อคลาย Python Global Interpreter Lock (GIL) ให้ Thread อื่นทำงานได้
- **Zero-Copy:** พยายามใช้ `&[u8]` หรือ `Bound<'py, PyArray>` แทนการสร้างสำเนาข้อมูลขนาดใหญ่ระหว่าง Python และ Rust

## 5. Documentation
- ใช้ `///` สำหรับ Documentation comments เหนือฟังก์ชันและ Struct
- ทุกฟังก์ชันที่เป็น Public (รวมถึงที่ export ไป Python) ต้องมีคำอธิบายอย่างน้อย 1 บรรทัด
- ให้ใส่ตัวอย่างการใช้งานใน `examples` folder ถ้า logic มีความซับซ้อน

## 6. Testing (TDD)
- **Unit Tests:** เขียนไว้ในไฟล์เดียวกับโค้ดภายใต้โมดูล `#[cfg(test)] mod tests`
- **Integration Tests:** เขียนไว้ในโฟลเดอร์ `tests/` ที่ root ของ engine crate
- **Property-based Testing:** ใช้ `proptest` สำหรับ Logic ที่สำคัญ (เช่น label parsing) เพื่อทดสอบ edge cases

## 7. Auto-Labeling & State Machine Logic
- **Exclusive Label Groups:** ออกแบบ Logic ให้รองรับการทำงานแบบ Exclusive ภายในกลุ่ม (e.g., หนึ่ง Issue มีได้เพียงหนึ่ง `state:*` label เท่านั้น)
- **Label Normalization:** Rust Engine ต้องสามารถลบ Label ที่เก่าหรือขัดแย้งกันออกได้โดยอัตโนมัติ
- **Validation Rules:**
  - `agent:*` ต้องมีเสมอหาก `state:*` ไม่ใช่ `backlog`
  - `status:blocked` จะถูกเพิ่มอัตโนมัติหากตรวจพบ label `blocking` หรือ `conflict`
- **Output Format:** ส่งคืนรายการ Label เป็น `Vec<String>` ที่เรียงลำดับและทำความสะอาดแล้ว (Sanitized) เพื่อให้ Python นำไป `PUT` ลง GitHub API ได้ทันที
