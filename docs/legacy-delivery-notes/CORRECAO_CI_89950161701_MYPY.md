# Correção CI 89950161701 — MyPy strict

## Falha observada

```text
app/services/builtin_template_package_service.py:71: error:
Returning Any from function declared to return "dict[str, Any]" [no-any-return]
```

O job passou por Compile Python e Ruff e parou exclusivamente no MyPy.

## Causa raiz

`json.loads()` possui retorno dinâmico (`Any`). A função `_builtin_manifest()` declara
explicitamente `dict[str, Any]`, portanto retornar diretamente o valor produzido por
`json.loads()` viola `no-any-return` no modo `strict` do MyPy.

## Correção

A leitura do manifesto agora segue o fluxo:

```text
json.loads(...)
  -> object
  -> validação isinstance(decoded, dict)
  -> cast(dict[str, Any], decoded)
  -> validação do schema/package.key
  -> retorno tipado
```

Não foi adicionado `# type: ignore`, não foi desabilitado `no-any-return` e não foi
criada exceção no `pyproject.toml`.

## Validação local

- 8/8 manifests oficiais carregados e conferidos;
- `python -m compileall -q app`: PASS;
- ARGWS Visual Builder 2.3.2: 81/81 testes PASS;
- `npm run check`: PASS.

O runtime local desta sessão não possui o executável `mypy`; a correção foi aplicada
no tipo apontado pelo GitHub Actions e será revalidada pelo mesmo job oficial da PR.
