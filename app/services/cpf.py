import itertools
import re


def calcular_digitos(cpf9: str) -> str:
    digits = [int(c) for c in cpf9]

    soma = sum(digits[i] * (10 - i) for i in range(9))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto

    digits.append(d1)
    soma = sum(digits[i] * (11 - i) for i in range(10))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto

    return f"{d1}{d2}"


def is_valido(cpf: str) -> bool:
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    if len(set(cpf)) == 1:
        return False
    return calcular_digitos(cpf[:9]) == cpf[9:]


def formatar(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def validate_cpf(cpf: str) -> dict:
    numeros = re.sub(r"\D", "", cpf)
    valido = is_valido(numeros)
    return {
        "valido": valido,
        "cpf_formatado": formatar(numeros) if len(numeros) == 11 else None,
        "cpf_numeros": numeros,
        "mensagem": "CPF válido." if valido else "CPF inválido.",
    }


# Curingas aceitos numa máscara — cobrem os formatos que aparecem na prática:
# mascaramento LGPD de documentos públicos (***.879.820-**), campo de formulário
# (151.879.___-95), planilha (151.879.###-95) e anotação manual (15X.879.82X-95,
# 151.879.???-95).
_MASK_WILDCARDS = "*Xx?_#"

# Separadores ignorados em qualquer posição — inclui o espaço não-quebrável, que
# vem junto quando a máscara é colada de PDF ou de página web.
_MASK_SEPARATORS = frozenset(".-/") | {"\\", " ", "\t", " "}

_DIGITS = "0123456789"


def _normalizar_mascara(mascara: str) -> list[str]:
    """Reduz qualquer formato de máscara a 11 posições contendo '0'-'9' ou '*'.

    Aceita qualquer curinga de _MASK_WILDCARDS e qualquer combinação de
    separadores (ou nenhum). Máscaras de 9 ou 10 posições têm os dígitos
    verificadores omitidos completados com curinga.
    """
    chars: list[str] = []
    for c in mascara:
        if c in _MASK_SEPARATORS:
            continue
        if c in _DIGITS:
            chars.append(c)
        elif c in _MASK_WILDCARDS:
            chars.append("*")
        else:
            raise ValueError(
                f"Caractere inválido na máscara: {c!r}. Use dígitos, "
                f"curingas ({' '.join(_MASK_WILDCARDS)}) ou separadores (. - / espaço)"
            )

    # DVs omitidos viram curinga: '151.879.820' e '151.879.820-9' são máscaras válidas
    if len(chars) in (9, 10):
        chars += ["*"] * (11 - len(chars))

    if len(chars) != 11:
        raise ValueError(
            f"Máscara deve ter 11 posições — ou 9/10, omitindo os dígitos "
            f"verificadores. Recebeu {len(chars)}: {mascara!r}"
        )

    return chars


def gerar_cpfs_de_mascara(mascara: str) -> list[str]:
    r"""Gera todos os CPFs válidos a partir de uma máscara com curingas.

    Curingas equivalentes: ``* X x ? _ #``
    Separadores ignorados: ponto, hífen, barra, contrabarra e espaços — de modo que
    ``***.879.820-**``, ``***879820**`` e ``*** 879 820 **`` são a mesma máscara.

    Os dígitos verificadores (posições 10-11) são sempre recalculados; quando
    informados na máscara, funcionam como filtro dos candidatos.
    """
    chars = _normalizar_mascara(mascara)

    # Posições 0-8 são a base; 9-10 são os verificadores
    base_template = chars[:9]
    check_template = chars[9:]

    wildcard_positions = [i for i, c in enumerate(base_template) if c == "*"]

    from app import config as _cfg
    if len(wildcard_positions) > _cfg.MAX_WILDCARDS_IN_MASK:
        limit = 10 ** _cfg.MAX_WILDCARDS_IN_MASK
        raise ValueError(
            f"Máscara tem {len(wildcard_positions)} curingas na base; "
            f"máximo permitido é {_cfg.MAX_WILDCARDS_IN_MASK} (~{limit:,} combinações)"
        )

    candidates = []
    for combo in itertools.product(_DIGITS, repeat=len(wildcard_positions)):
        base = list(base_template)
        for pos, digit in zip(wildcard_positions, combo):
            base[pos] = digit
        base9 = "".join(base)
        digits = calcular_digitos(base9)
        if check_template[0] != "*" and check_template[0] != digits[0]:
            continue
        if check_template[1] != "*" and check_template[1] != digits[1]:
            continue
        cpf11 = base9 + digits
        if is_valido(cpf11):
            candidates.append(cpf11)

    return candidates


def generate_valid_variations(cpf: str) -> dict:
    numeros = re.sub(r"\D", "", cpf)
    if len(numeros) != 11:
        return {"error": f"CPF deve ter 11 dígitos, recebido {len(numeros)}", "variations": []}
    original_valido = is_valido(numeros)

    seen = set()
    variations = []

    def add(candidate: str):
        if candidate not in seen and is_valido(candidate):
            seen.add(candidate)
            variations.append({"cpf_numeros": candidate, "cpf_formatado": formatar(candidate)})

    # original
    add(numeros)

    # recalculate check digits
    if len(numeros) >= 9:
        recalc = numeros[:9] + calcular_digitos(numeros[:9])
        add(recalc)

    # swap one digit in any of the 11 positions, keeping the other 10 as typed.
    # Recalculating the check digits here would accept every one of the 81 base
    # swaps (any base has valid check digits) — candidates up to 3 digits away
    # from the input, which is not a single-digit typo.
    for i in range(11):
        for d in _DIGITS:
            if d != numeros[i]:
                add(numeros[:i] + d + numeros[i + 1:])

    # transpose adjacent digits
    for i in range(10):
        lst = list(numeros)
        lst[i], lst[i + 1] = lst[i + 1], lst[i]
        candidate = "".join(lst)
        add(candidate)

    return {
        "original": numeros,
        "original_valido": original_valido,
        "total_variacoes": len(variations),
        "variations": variations,
    }
