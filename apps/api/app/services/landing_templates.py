from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _block(block_type: str, **props: Any) -> dict[str, Any]:
    return {
        "id": _id(block_type),
        "type": block_type,
        "props": props,
        "style": {},
        "responsive": {
            "desktop": {},
            "tablet": {},
            "mobile": {},
            "hidden": {"desktop": False, "tablet": False, "mobile": False},
        },
    }


def _page(
    *,
    title: str,
    primary: str,
    secondary: str,
    accent: str,
    background: str,
    text: str,
    heading_font: str,
    body_font: str,
    radius: int,
    blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "version": 2,
        "title": title,
        "global_styles": {
            "primary": primary,
            "secondary": secondary,
            "accent": accent,
            "background": background,
            "text": text,
            "heading_font": heading_font,
            "body_font": body_font,
            "radius": radius,
            "button_style": "solid",
        },
        "seo": {
            "title": title,
            "description": "Agende seu horário online.",
            "share_image": "",
            "canonical_url": "",
        },
        "blocks": blocks,
    }


TEMPLATES: dict[str, dict[str, Any]] = {
    "martelinho-de-ouro": {
        "key": "martelinho-de-ouro",
        "name": "Martelinho de Ouro",
        "description": "Página visual para avaliação, reparos automotivos e antes/depois.",
        "segment": "automotivo",
        "content": _page(
            title="Martelinho de Ouro",
            primary="#e6a817",
            secondary="#111827",
            accent="#f4c84b",
            background="#f7f7f5",
            text="#171717",
            heading_font="Inter",
            body_font="Inter",
            radius=16,
            blocks=[
                _block("hero", eyebrow="Especialista em reparos sem pintura", title="Seu veículo impecável novamente", text="Avaliação rápida, atendimento profissional e acabamento cuidadoso.", cta="Agendar avaliação", image=""),
                _block("gallery", title="Antes e depois", layout="before_after", images=[]),
                _block("services", title="Serviços", subtitle="Escolha a avaliação ideal para o seu veículo", show_prices=True),
                _block("cards", title="Por que escolher nosso trabalho", items=[{"title":"Avaliação cuidadosa","text":"Análise individual de cada dano."},{"title":"Acabamento profissional","text":"Técnica e atenção aos detalhes."},{"title":"Atendimento agendado","text":"Escolha o melhor horário."}]),
                _block("testimonials", title="Quem já trouxe o veículo", items=[]),
                _block("address", title="Onde estamos", address="", show_map=True),
                _block("booking", title="Agendar avaliação", subtitle="Escolha profissional, data e horário."),
                _block("whatsapp_button", label="Falar pelo WhatsApp", phone=""),
                _block("footer", text="Atendimento com hora marcada."),
            ],
        ),
    },
    "cabeleireiro": {
        "key": "cabeleireiro",
        "name": "Cabeleireiro",
        "description": "Página mobile-first para cabeleireiros, barbeiros e salões.",
        "segment": "beleza",
        "content": _page(
            title="Cabeleireiro",
            primary="#1f2937",
            secondary="#f5efe8",
            accent="#bd8b5f",
            background="#fffdfa",
            text="#201d1b",
            heading_font="Playfair Display",
            body_font="Inter",
            radius=22,
            blocks=[
                _block("hero", eyebrow="Beleza com hora marcada", title="Seu estilo, no seu horário", text="Atendimento personalizado para você sair se sentindo ainda melhor.", cta="Escolher horário", image=""),
                _block("professionals", title="Profissional", layout="spotlight"),
                _block("services", title="Serviços e valores", subtitle="Encontre o cuidado ideal", show_prices=True),
                _block("gallery", title="Portfólio", layout="masonry", images=[]),
                _block("testimonials", title="Avaliações", items=[]),
                _block("social", title="Acompanhe nosso trabalho", instagram="", facebook=""),
                _block("booking", title="Reserve seu horário", subtitle="Poucos passos e pronto."),
                _block("business_hours", title="Horários de atendimento"),
                _block("address", title="Localização", address="", show_map=True),
                _block("footer", text="Esperamos por você."),
            ],
        ),
    },
    "studio-neils": {
        "key": "studio-neils",
        "name": "Studio Neils",
        "description": "Modelo visual e elegante para manicure, nail designer e estética.",
        "segment": "beleza-visual",
        "content": _page(
            title="Studio Neils",
            primary="#b35b79",
            secondary="#fff0f5",
            accent="#e6a5bb",
            background="#fffafd",
            text="#3a2530",
            heading_font="DM Serif Display",
            body_font="Inter",
            radius=26,
            blocks=[
                _block("hero", eyebrow="Studio de beleza", title="Detalhes que fazem você se sentir única", text="Seu momento de cuidado com atendimento marcado e experiência especial.", cta="Agendar agora", image=""),
                _block("gallery", title="Trabalhos recentes", layout="editorial", images=[]),
                _block("services", title="Experiências do Studio", subtitle="Escolha seu atendimento", show_prices=True),
                _block("professionals", title="Quem cuida de você", layout="cards"),
                _block("gallery", title="Inspirações", layout="carousel", images=[]),
                _block("testimonials", title="Clientes do Studio", items=[]),
                _block("social", title="Veja mais no Instagram", instagram="", tiktok=""),
                _block("booking", title="Escolha seu horário", subtitle="Agende de forma simples pelo celular."),
                _block("cta", title="Pronta para seu próximo cuidado?", text="Escolha um horário disponível.", button="Ver agenda"),
                _block("footer", text="Studio Neils"),
            ],
        ),
    },
    "clinica": {
        "key": "clinica",
        "name": "Clínica",
        "description": "Modelo sóbrio para consultórios, odontologia, psicologia e clínicas.",
        "segment": "saude",
        "content": _page(
            title="Clínica",
            primary="#176b87",
            secondary="#eef8fa",
            accent="#42a7b7",
            background="#f8fbfc",
            text="#16313b",
            heading_font="Inter",
            body_font="Inter",
            radius=14,
            blocks=[
                _block("hero", eyebrow="Atendimento profissional", title="Cuidado com confiança e horário marcado", text="Conheça nossa equipe e escolha o melhor horário para seu atendimento.", cta="Agendar atendimento", image=""),
                _block("services", title="Especialidades", subtitle="Áreas de atendimento", show_prices=False),
                _block("professionals", title="Profissionais", layout="credentials"),
                _block("cards", title="Atendimento", items=[{"title":"Agendamento simples","text":"Escolha data e horário."},{"title":"Equipe profissional","text":"Conheça os profissionais disponíveis."},{"title":"Informações claras","text":"Local, horário e contato em um só lugar."}]),
                _block("address", title="Unidades e localização", address="", show_map=True),
                _block("business_hours", title="Horários"),
                _block("faq", title="Dúvidas frequentes", items=[]),
                _block("booking", title="Agende seu atendimento", subtitle="Solicitamos apenas os dados necessários para a agenda."),
                _block("contact", title="Contato", phone="", email=""),
                _block("policies", title="Informações importantes", text="O agendamento não substitui orientações profissionais ou atendimento de urgência."),
                _block("footer", text="Atendimento mediante agendamento."),
            ],
        ),
    },
    "servicos": {
        "key": "servicos",
        "name": "Serviços",
        "description": "Modelo para suporte, implantação, treinamento, manutenção e consultoria.",
        "segment": "servicos",
        "content": _page(
            title="Serviços",
            primary="#2157d5",
            secondary="#101c37",
            accent="#30b8d8",
            background="#f5f8ff",
            text="#16213a",
            heading_font="Inter",
            body_font="Inter",
            radius=15,
            blocks=[
                _block("hero", eyebrow="Atendimento especializado", title="Reserve o suporte certo para sua necessidade", text="Suporte, implantação, treinamento, visita técnica e consultoria com horário organizado.", cta="Agendar serviço", image=""),
                _block("services", title="Como podemos ajudar", subtitle="Selecione a modalidade de atendimento", show_prices=True),
                _block("cards", title="Formatos de atendimento", items=[{"title":"Remoto","text":"Atendimento online e suporte assistido."},{"title":"Presencial","text":"Visita técnica com horário reservado."},{"title":"Consultivo","text":"Sessões de análise, implantação e treinamento."}]),
                _block("professionals", title="Especialistas", layout="compact"),
                _block("booking", title="Escolha data e horário", subtitle="Reserve o atendimento adequado."),
                _block("faq", title="Perguntas frequentes", items=[]),
                _block("contact", title="Precisa falar conosco?", phone="", email=""),
                _block("footer", text="Atendimento organizado para sua operação."),
            ],
        ),
    },
    "reunioes": {
        "key": "reunioes",
        "name": "Reuniões",
        "description": "Fluxo direto para reuniões pessoais, comerciais, clubes e mentorias.",
        "segment": "reunioes",
        "content": _page(
            title="Reuniões",
            primary="#5146d8",
            secondary="#17152f",
            accent="#8f86ff",
            background="#faf9ff",
            text="#25223d",
            heading_font="Inter",
            body_font="Inter",
            radius=18,
            blocks=[
                _block("hero", eyebrow="Agenda de reuniões", title="Vamos encontrar um horário", text="Escolha responsável, data e horário de forma rápida.", cta="Ver disponibilidade", image=""),
                _block("booking", title="Agendar reunião", subtitle="Responsável → data → horário → seus dados."),
                _block("cards", title="Tipos de encontro", items=[{"title":"Pessoal","text":"Conversa ou compromisso individual."},{"title":"Corporativo","text":"Reunião comercial ou de equipe."},{"title":"Mentoria e consultoria","text":"Sessão com duração definida."}]),
                _block("business_hours", title="Disponibilidade"),
                _block("faq", title="Antes da reunião", items=[]),
                _block("contact", title="Contato", phone="", email=""),
                _block("footer", text="Reuniões com horário reservado."),
            ],
        ),
    },
    "agenda-essencial": {
        "key": "agenda-essencial",
        "name": "Agenda Essencial",
        "description": "Modelo neutro, rápido e altamente editável para qualquer segmento.",
        "segment": "generico",
        "content": _page(
            title="Agenda Essencial",
            primary="#3151cf",
            secondary="#151c31",
            accent="#6d72ef",
            background="#f7f8fc",
            text="#1d273a",
            heading_font="Inter",
            body_font="Inter",
            radius=16,
            blocks=[
                _block("hero", eyebrow="Agendamento online", title="Escolha seu horário", text="Uma página direta para apresentar seu negócio e receber agendamentos.", cta="Agendar", image=""),
                _block("text", title="Sobre", text="Conte aqui, de forma breve, o que torna seu atendimento especial."),
                _block("services", title="Serviços", subtitle="Opções disponíveis", show_prices=True),
                _block("professionals", title="Profissionais", layout="compact"),
                _block("booking", title="Agenda", subtitle="Escolha a melhor data e horário."),
                _block("contact", title="Contato", phone="", email=""),
                _block("footer", text="Obrigado pela visita."),
            ],
        ),
    },
}


def list_templates() -> list[dict[str, Any]]:
    return [
        {key: value[key] for key in ("key", "name", "description", "segment")}
        for value in TEMPLATES.values()
    ]


def template_content(key: str) -> dict[str, Any]:
    template = TEMPLATES.get(key)
    if template is None:
        raise KeyError(key)
    return deepcopy(template["content"])
