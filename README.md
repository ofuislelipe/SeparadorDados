
# 📂 Processamento Automático de Arquivos CSV

Este projeto em **Streamlit** automatiza o processamento e classificação de arquivos CSV com base em regras de negócio predefinidas. Ele permite o upload de múltiplos arquivos e os classifica conforme o tipo e conteúdo, gerando uma estrutura organizada e um pacote `.zip` com os resultados.

## ✅ Funcionalidades

- Upload de um arquivo de **mapeamento de proprietários** (`proprietarios.csv`)
- Upload de múltiplos **arquivos CSV** de dados
- Identificação automática do **tipo de arquivo** baseado no nome
- Aplicação de **regras de classificação** personalizadas
- Geração de arquivos organizados por destino (pasta)
- Inclusão de **log** com proprietários não encontrados
- Download de resultados em um único arquivo **.zip**

---

## 📁 Estrutura das Regras

### Regras implementadas:

- `time_de_dados`: Arquivos do time de dados (identificados por prefixos como `10 -`, `11 -`, etc.)
- `canal`: Usa a coluna `tipo_de_origem` para definir se vai para `Central` ou `Cesar`
- `data_criacao`: Usa `canal` e `tipo_de_origem` para decidir entre `Cesar`, `Central`, ou `Brenda`
- `diretoria`: Mesma regra da `data_criacao`
- `proprietario`: Baseado em mapeamento do nome completo do proprietário
- `prazo_regulamentar`: Usa `tipo_de_origem`, mas pode cair no mapeamento de proprietário também

---

## 📌 Pré-requisitos

- Python 3.8+
- Instalar dependências:
  
```bash
pip install -r requirements.txt
```

**Exemplo de `requirements.txt`:**

```
streamlit
pandas
unidecode
```

---

## ▶️ Como usar

1. Execute o aplicativo:
```bash
streamlit run app.py
```

2. No navegador:
   - Faça o upload do arquivo `proprietarios.csv`
   - Faça o upload de todos os arquivos CSV de dados
   - Clique em "Processar Todos os Arquivos"
   - Baixe o `.zip` com os resultados

---

## 🧠 Estrutura esperada do mapeamento (`proprietarios.csv`)

| proprietario_nome_completo | escritorio |
|----------------------------|------------|
| Fulano da Silva            | Cesar      |
| Maria Oliveira             | Central    |

---

## 📤 Resultado final

- Arquivos são agrupados em pastas conforme a regra de destino
- Os arquivos no `.zip` mantêm os nomes originais
- Um log é incluído caso existam proprietários não encontrados

---


