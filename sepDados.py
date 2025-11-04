import streamlit as st
import pandas as pd
import io
import zipfile
import os
import re
from unidecode import unidecode

st.title("Processamento Automático de Arquivos CSV")

# ============================================================================
#                            FUNÇÕES DE REGRAS COMPLETAS
# ============================================================================

def normalize_columns(df):
    """Normaliza nomes de colunas para snake_case sem caracteres especiais"""
    df.columns = [
        unidecode(col).strip().lower()
        .replace(' ', '_')
        .replace('-', '_')
        .replace('(', '')
        .replace(')', '')
        for col in df.columns
    ]
    return df

def get_folder_canal(row):
    """Regra para CANAL, PROSPECT_ESTADO, CLIENTE_CIDADE e CLIENTE_CEP"""
    tipo = str(row.get('tipo_de_origem', '')).strip().lower()
    return 'Central' if tipo in ['cliente', 'canal_telefone', 'web'] else 'Bruno Vanderlei'

def get_folder_data_criacao(row):
    """Regra para DATA_HORA_CRIACAO (Usada pela Regra Diretoria)"""
    canal_val = str(row.get('canal', '')).strip().lower()
    if canal_val == 'ouvidoria_caixa':
        return 'Bruno Vanderlei'
    elif canal_val == 'consumidor.gov':
        return 'Central'
    elif canal_val == 'canal_de_denúncias':
        return 'Brenda'
    
    tipo = str(row.get('tipo_de_origem', '')).strip().lower()
    return 'Bruno Vanderlei' if tipo in ['procon', 'rdr', 'nip', 'e-mail', 'bacen'] else 'Central'

def get_folder_diretoria(row):
    """Regra para DIRETORIA"""
    return get_folder_data_criacao(row)

def get_folder_proprietario(row, mapping):
    """Regra com normalização avançada de nomes"""
    raw_name = str(row.get('proprietario_nome_completo', '')).strip()
    normalized_name = unidecode(raw_name).lower().strip()
    
    for mapped_name, escritorio in mapping.items():
        if unidecode(mapped_name).lower().strip() == normalized_name:
            return escritorio
    return 'Proprietario_Nao_Encontrado'

# --- MUDANÇA (2/4): ADICIONADA NOVA FUNÇÃO PARA REGRA 'CRIADO POR' ---
def get_folder_criado_por(row, mapping):
    """Regra para 'Criado Por' (Arquivo 22) baseada no mapeamento"""
    # Usa a coluna 'criado_por_nome_completo'
    raw_name = str(row.get('criado_por_nome_completo', '')).strip()
    normalized_name = unidecode(raw_name).lower().strip()
    
    # Reutiliza o mesmo 'prop_mapping' (o arquivo proprietarios.csv)
    for mapped_name, escritorio in mapping.items():
        if unidecode(mapped_name).lower().strip() == normalized_name:
            return escritorio
    # Retorna o mesmo erro para ser pego pelo log de proprietários
    return 'Proprietario_Nao_Encontrado'
# --------------------------------------------------------------------

def get_folder_prazo_regulamentar(row, mapping):
    """Regra especial para PRAZO_REGULAMENTAR"""
    tipo = str(row.get('tipo_de_origem', '')).strip().lower()
    return 'Bruno Vanderlei' if tipo == 'procon_audiência' else get_folder_proprietario(row, mapping)

# ============================================================================
#                            FUNÇÕES DE SUPORTE
# ============================================================================

def detect_file_type(file_name):
    """Identifica o tipo de arquivo pelo padrão no nome"""
    patterns = {
        'time_de_dados': r'(10 -|11 -|12 -|20 -|14 -|15 -|29 -|41)',
        'canal': r'(16 -|38 -|39 -|43 - |05 -)',
        'diretoria': r'18 -',
        # 'data_criacao': r'22 -', # <-- Linha antiga removida
        'proprietario': r'(26 -|28 -|34 -|36 -|35 -)',
        'prazo_regulamentar': r'27 -',
        'criado_por': r'22 -' # --- MUDANÇA (1/4): Arquivo 22 agora é 'criado_por' ---
    }
    
    for key, pattern in patterns.items():
        if re.search(pattern, file_name, flags=re.IGNORECASE):
            return key
    return None

def apply_rule(file_type, row, mapping):
    """Aplica a regra correspondente ao tipo de arquivo"""
    try:
        if file_type == 'time_de_dados':
            return "time_de_dados"
        elif file_type == 'canal':
            return get_folder_canal(row)
        elif file_type == 'diretoria':
            return get_folder_diretoria(row)
        elif file_type == 'data_criacao':
            # Esta regra ainda existe para o caso 'diretoria' (arquivo 18)
            return get_folder_data_criacao(row)
        elif file_type == 'proprietario':
            return get_folder_proprietario(row, mapping)
        
        # --- MUDANÇA (3/4): ADICIONADA NOVA CONDIÇÃO 'criado_por' ---
        elif file_type == 'criado_por':
            return get_folder_criado_por(row, mapping)
        # -----------------------------------------------------------
            
        elif file_type == 'prazo_regulamentar':
            return get_folder_prazo_regulamentar(row, mapping)
        return 'NaoClassificado'
    except Exception as e:
        return f'Erro: {str(e)}'

# ============================================================================
#                            INTERFACE E PROCESSAMENTO
# ============================================================================

# 1. Upload do mapeamento
st.header("1. Upload do Arquivo de Mapeamento")
mapping_file = st.file_uploader(
    "Carregar proprietarios.csv",
    type=["csv"],
    key="mapping"
)

prop_mapping = {}
if mapping_file:
    try:
        # Tentar diferentes combinações de encoding/delimitador
        try:
            df_mapping = pd.read_csv(mapping_file, sep=None, engine='python', encoding='utf-8')
        except UnicodeDecodeError:
            df_mapping = pd.read_csv(mapping_file, sep=None, engine='python', encoding='latin-1')
        
        df_mapping = normalize_columns(df_mapping)
        
        # Verificar colunas obrigatórias
        required_columns = {'proprietario_nome_completo', 'escritorio'}
        if not required_columns.issubset(df_mapping.columns):
            st.error(f"""
            Colunas obrigatórias não encontradas!
            Esperado: {required_columns}
            Encontrado: {list(df_mapping.columns)}
            """)
            st.stop()
            
        # Criar dicionário normalizado
        prop_mapping = {}
        for _, row in df_mapping.iterrows():
            key = unidecode(row['proprietario_nome_completo']).lower().strip()
            value = row['escritorio'].strip()
            prop_mapping[key] = value
        
        st.success(f"Mapeamento carregado com {len(prop_mapping)} registros!")
        
    except Exception as e:
        st.error(f"Erro crítico: {str(e)}")
        st.stop()

# 2. Upload de arquivos
st.header("2. Upload de Todos os Arquivos CSVs")
all_files = st.file_uploader(
    "Arraste todos os arquivos CSV aqui (pode selecionar múltiplos)",
    type=["csv"],
    accept_multiple_files=True
)

# 3. Processamento
if st.button("Processar Todos os Arquivos") and all_files:
    output_files = {}
    missing_proprietarios = set()
    required_columns_map = {
        'proprietario': ['proprietario_nome_completo'],
        'prazo_regulamentar': ['proprietario_nome_completo', 'tipo_de_origem'],
        'canal': ['tipo_de_origem'],
        'data_criacao': ['canal', 'tipo_de_origem'], # (Mantido para a regra 'diretoria')
        'diretoria': ['tipo_de_origem'],
        'criado_por': ['criado_por_nome_completo'] # --- MUDANÇA (4/4): Coluna obrigatória adicionada ---
    }
    
    for file_obj in all_files:
        try:
            file_name = file_obj.name
            file_type = detect_file_type(file_name)
            
            if not file_type:
                st.warning(f"Arquivo não classificado: {file_name}")
                continue

            # Ler e normalizar
            try:
                df = pd.read_csv(file_obj, sep=None, engine='python', encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_obj, sep=None, engine='python', encoding='latin-1')
            
            df = normalize_columns(df)
            
            # Verificar colunas obrigatórias
            if file_type in required_columns_map:
                missing = [col for col in required_columns_map[file_type] if col not in df.columns]
                if missing:
                    # Agora o erro será "Colunas obrigatórias faltando: ['criado_por_nome_completo']"
                    raise ValueError(f"Colunas obrigatórias faltando: {missing}")

            # Aplicar regras
            df["destino"] = df.apply(
                lambda row: apply_rule(file_type, row, prop_mapping), 
                axis=1
            )
            
            # Registrar problemas
            if 'Proprietario_Nao_Encontrado' in df['destino'].values:
                # Se a regra 'criado_por' falhar, ela também cairá aqui
                if file_type == 'proprietario' or file_type == 'prazo_regulamentar':
                    missing_df = df[df['destino'] == 'Proprietario_Nao_Encontrado']
                    missing_proprietarios.update(missing_df['proprietario_nome_completo'].unique())
                elif file_type == 'criado_por':
                    missing_df = df[df['destino'] == 'Proprietario_Nao_Encontrado']
                    missing_proprietarios.update(missing_df['criado_por_nome_completo'].unique())
                
                st.warning(f"⚠️ {file_name}: {len(missing_df)} registros não mapeados")

            # Salvar resultados
            for destino, group in df.groupby("destino"):
                buffer = io.StringIO()
                group.to_csv(buffer, index=False, sep=";", encoding='utf-8-sig')
                path = os.path.join(destino, file_name)
                output_files[path] = buffer.getvalue()
                
            st.success(f"✅ {file_name} processado como {file_type}")

        except Exception as e:
            st.error(f"❌ Erro em {file_name}: {str(e)}")
            continue
    
    # Gerar arquivo final
    if output_files:
        # Adicionar log de problemas
        if missing_proprietarios:
            log_content = "Proprietários/Criados Por não encontrados:\n" + "\n".join(sorted(missing_proprietarios))
            output_files['Proprietario_Nao_Encontrado/log_proprietarios.txt'] = log_content
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for path, content in output_files.items():
                zf.writestr(path, content.encode('utf-8'))
        
        st.download_button(
            "⬇️ Baixar Resultados",
            data=zip_buffer.getvalue(),
            file_name="resultados_processamento.zip",
            mime="application/zip"
        )
    else:
        st.error("Nenhum arquivo foi processado com sucesso")