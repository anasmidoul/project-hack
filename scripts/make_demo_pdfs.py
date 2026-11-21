"""Create selectable, fictional documents used by the HOUSIA demo and tests."""
from __future__ import annotations

from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "housia" / "static" / "demo"

DOCUMENTS = {
    "payslip-demo.pdf": [
        "FICTIONAL DOCUMENT - HOUSIA DEMO", "PAYSLIP - NOVEMBER 2026",
        "Name: Dani Lopez", "DNI: 12345678Z", "Employer: Example Madrid SL",
        "Net monthly pay: 2,100 EUR", "IBAN: ES9121000418450200051332",
        "Address: Calle Falsa 123, Madrid",
    ],
    "enrolment-demo.pdf": [
        "FICTIONAL DOCUMENT - HOUSIA DEMO", "ENROLMENT CERTIFICATE",
        "Full name: Cris Gomez", "Passport: ABC123456", "Institution: Demo University",
        "Academic year: 2026-2027", "Address: Avenida Demo 42, Valencia",
    ],
    "signed-contract-demo.pdf": [
        "FICTIONAL DOCUMENT - HOUSIA DEMO", "SIGNED RENTAL AGREEMENT",
        "Tenant: Dani Lopez", "DNI: 12345678Z", "IBAN: ES9121000418450200051332",
        "Rental address: Calle de Ibiza 14, Madrid", "Monthly rent: 950 EUR",
        "This fictional agreement is for demonstration only.",
    ],
}


def _pdf(lines: list[str]) -> bytes:
    """Write a small one-page PDF using only built-in fonts and standard-library code."""
    escaped = [line.encode("ascii", "replace").decode("ascii").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    commands = ["BT", "/F1 16 Tf", "50 760 Td"]
    for index, line in enumerate(escaped):
        if index == 1:
            commands.extend(["/F1 13 Tf", "0 -34 Td"])
        elif index:
            commands.append("0 -27 Td")
        commands.append(f"({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n%HOUSIA DEMO\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_at = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode())
    return bytes(output)

def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, lines in DOCUMENTS.items():
        (OUTPUT / filename).write_bytes(_pdf(lines))
        print(f"Wrote {OUTPUT / filename}")


if __name__ == "__main__":
    main()
