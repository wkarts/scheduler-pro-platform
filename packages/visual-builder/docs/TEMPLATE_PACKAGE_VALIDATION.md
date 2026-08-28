# Validação dos pacotes Scheduler Pro anexados — 2.2.0

Data: 2026-08-27

Os sete pacotes fornecidos foram importados programaticamente nas duas superfícies disponíveis (`landing` e `booking`) usando exatamente o importador distribuído em `src/template-packages.js`.

| Pacote | Template key | Landing | Booking |
|---|---|---:|---:|
| Barber Shop — Neo Genérico | `barber-shop-neo-generico` | OK | OK |
| Clínica Médica — Genérico | `clinica-medica-generico` | OK | OK |
| Clínica Veterinária — Genérico | `clinica-veterinaria-generico` | OK | OK |
| Clínica Odontológica — Genérico | `clinica-odontologica-generico` | OK | OK |
| Studio de Unhas — Genérico | `studio-unhas-generico` | OK | OK |
| Martelinho de Ouro — Genérico | `martelinho-de-ouro-generico` | OK | OK |
| Tecnologia — Genérico Simples | `tecnologia-generico-simples` | OK | OK |

Em cada caso foram confirmados:

- leitura do ZIP;
- `template.json` no schema `scheduler-pro-template-package/v1`;
- resolução das entradas `landing.html` e `agendamento.html`;
- meta `scheduler-pro-template`;
- superfície `LANDING`/`BOOKING`;
- conversão para `html_surface`;
- recompilação para `scheduler-pro-html-template/v1`;
- preservação integral de `html_document`.
