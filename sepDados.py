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
    # ATUALIZADO: 'tipo_de_origem' para 'tp_origem'
    tipo = str(row.get('tp_origem', '')).strip().lower()
    return 'Central' if tipo in ['CLIENTE','CLIENTE ODONTO', 'CLIENTE SAÚDE'] else 'Bruno Vanderlei'

def get_folder_data_criacao(row):
    """Regra para DATA_HORA_CRIACAO"""
    canal_val = str(row.get('canal', '')).strip().lower()
    if canal_val == 'Ouvidoria – CAIXA':
        return 'Bruno Vanderlei'
    elif canal_val == 'Consumidor.GOV':
        return 'Central'
    elif canal_val == 'Bruno Vanderlei':
        return 'Ouvidoria'

    tipo = str(row.get('tp_origem', '')).strip().lower()
    return 'Bruno Vanderlei' if tipo in ['PROCON','PROCON – Audiência','PROCON – Auto de Infração','PROCON – Multa','Procon - Reclamação','PROCON- MULTA','PROCON–CIP', 'BACEN', 'NIP Assistencial','NIP não Assistencial','ANS'] else 'Central'

def get_folder_diretoria(row, mapping):
    """Regra para DIRETORIA (baseada no Proprietário)"""
    return get_folder_proprietario(row, mapping)

def get_folder_proprietario(row, mapping):
    """Regra com normalização avançada de nomes"""
    raw_name = str(row.get('nome_proprietario_caso', '')).strip()
    normalized_name = unidecode(raw_name).lower().strip()
    
    for mapped_name, escritorio in mapping.items():
        if unidecode(mapped_name).lower().strip() == normalized_name:
            return escritorio
    return 'Proprietario_Nao_Encontrado'

def get_folder_criado_por(row, mapping):
    """Regra para 'Criado Por' (Arquivo 22) baseada no mapeamento"""
    raw_name = str(row.get('criado_por', '')).strip()
    normalized_name = unidecode(raw_name).lower().strip()
    
    for mapped_name, escritorio in mapping.items():
        if unidecode(mapped_name).lower().strip() == normalized_name:
            return escritorio
    return 'Proprietario_Nao_Encontrado'

def get_folder_prazo_regulamentar(row, mapping):
    """Regra especial para PRAZO_REGULAMENTAR"""
    tipo = str(row.get('tp_origem', '')).strip().lower()
    return 'Bruno Vanderlei' if tipo == 'procon_audiência' else get_folder_proprietario(row, mapping)

# ============================================================================
#                            FUNÇÕES DE SUPORTE
# ============================================================================

def detect_file_type(file_name):
    """Identifica o tipo de arquivo pelo padrão no nome"""
    patterns = {
        'time_de_dados': r'(10 -|11 -|12 -|20 -|14 -|15 -|29 -|39)',
        'canal': r'(16 -|37 -|38 -|40 - |04 -)',
        'diretoria': r'18 -',
        'proprietario': r'(26 -|28 -|34 -|36 -|35 -)',
        'prazo_regulamentar': r'27 -',
        'criado_por': r'22 -'
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
            return get_folder_data_criacao(row)
        elif file_type == 'proprietario':
            return get_folder_proprietario(row, mapping)
        elif file_type == 'criado_por':
            return get_folder_criado_por(row, mapping)
        elif file_type == 'prazo_regulamentar':
            return get_folder_prazo_regulamentar(row, mapping)
        return 'NaoClassificado'
    except Exception as e:
        return f'Erro: {str(e)}'
    
# ============================================================================
#                            INTERFACE E PROCESSAMENTO
# ============================================================================

st.header("1. Upload do Arquivo de Mapeamento")
mapping_file = st.file_uploader(
    "Carregar proprietarios.csv",
    type=["csv"],
    key="mapping"
)

prop_mapping = {}
if mapping_file:
    try:
        try:
            df_mapping = pd.read_csv(mapping_file, sep=None, engine='python', encoding='utf-8')
        except UnicodeDecodeError:
            df_mapping = pd.read_csv(mapping_file, sep=None, engine='python', encoding='latin-1')
        
        df_mapping = normalize_columns(df_mapping)
        
        # Mantivemos 'proprietario_nome_completo' aqui assumindo que o CSV de mapeamento não mudou de formato
        required_columns = {'proprietario_nome_completo', 'escritorio'}
        if not required_columns.issubset(df_mapping.columns):
            st.error(f"""
            Colunas obrigatórias não encontradas no arquivo de mapeamento!
            Esperado: {required_columns}
            Encontrado: {list(df_mapping.columns)}
            """)
            st.stop()
            
        prop_mapping = {}
        for _, row in df_mapping.iterrows():
            key = unidecode(row['proprietario_nome_completo']).lower().strip()
            value = row['escritorio'].strip()
            prop_mapping[key] = value
        
        st.success(f"Mapeamento carregado com {len(prop_mapping)} registros!")
        
    except Exception as e:
        st.error(f"Erro crítico no mapeamento: {str(e)}")
        st.stop()

st.header("2. Upload de Todos os Arquivos CSVs")
all_files = st.file_uploader(
    "Arraste todos os arquivos CSV aqui (pode selecionar múltiplos)",
    type=["csv"],
    accept_multiple_files=True
)

if st.button("Processar Todos os Arquivos") and all_files:
    output_files = {}
    missing_proprietarios = set()
    
    # ATUALIZADO: Novas colunas mapeadas na validação obrigatória
    required_columns_map = {
        'proprietario': ['nome_proprietario_caso'],
        'prazo_regulamentar': ['nome_proprietario_caso', 'tp_origem'],
        'canal': ['tp_origem'],
        'data_criacao': ['canal', 'tp_origem'], 
        'diretoria': ['tp_origem'],
        'criado_por': ['criado_por'] 
    }
    
    for file_obj in all_files:
        try:
            file_name = file_obj.name
            file_type = detect_file_type(file_name)
            
            if not file_type:
                st.warning(f"Arquivo não classificado: {file_name}")
                continue

            try:
                df = pd.read_csv(file_obj, sep=None, engine='python', encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_obj, sep=None, engine='python', encoding='latin-1')
            
            df = normalize_columns(df)
            
            if file_type in required_columns_map:
                missing = [col for col in required_columns_map[file_type] if col not in df.columns]
                if missing:
                    raise ValueError(f"Colunas obrigatórias faltando: {missing}")

            df["destino"] = df.apply(
                lambda row: apply_rule(file_type, row, prop_mapping), 
                axis=1
            )
            
            # CORRIGIDO: Bug de escopo da variável missing_df e colunas atualizadas
            if 'Proprietario_Nao_Encontrado' in df['destino'].values:
                missing_df = df[df['destino'] == 'Proprietario_Nao_Encontrado'] # Declarado antes dos IFs
                
                if file_type in ['proprietario', 'prazo_regulamentar']:
                    missing_proprietarios.update(missing_df['nome_proprietario_caso'].unique())
                elif file_type == 'criado_por':
                    missing_proprietarios.update(missing_df['criado_por'].unique())
                
                st.warning(f"⚠️ {file_name}: {len(missing_df)} registros não mapeados")

            for destino, group in df.groupby("destino"):
                buffer = io.StringIO()
                group.to_csv(buffer, index=False, sep=";", encoding='utf-8-sig')
                path = os.path.join(destino, file_name)
                output_files[path] = buffer.getvalue()
                
            st.success(f"✅ {file_name} processado como {file_type}")

        except Exception as e:
            st.error(f"❌ Erro em {file_name}: {str(e)}")
            continue
    
    if output_files:
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