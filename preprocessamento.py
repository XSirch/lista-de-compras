#!/usr/bin/env python3
"""
Sistema de Pré-processamento Inteligente com CrewAI
Otimiza descrições de produtos para melhor descoberta de preços.
"""

import pandas as pd
import os
import logging
from datetime import datetime
from typing import List
from dataclasses import dataclass
from dotenv import load_dotenv

# CrewAI imports
from crewai import Agent, Task, Crew, Process

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ItemResult:
    """Resultado do processamento de um item"""
    original: str
    optimized: str
    notes: str

class SmartPreprocessor:
    """Sistema inteligente de pré-processamento com CrewAI"""

    def __init__(self):
        """Inicializa o sistema"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY não encontrada nas variáveis de ambiente")

        # Agente especialista em otimização de produtos brasileiros
        self.optimizer_agent = Agent(
            role="Especialista em E-commerce Brasileiro",
            goal="Otimizar descrições de produtos para busca em e-commerces brasileiros",
            backstory="""Você é um especialista em terminologia de e-commerce brasileiro.
            Sua missão é reescrever descrições de produtos para maximizar a precisão
            das buscas, mantendo o significado original e usando termos que consumidores
            brasileiros realmente pesquisam.""",
            verbose=False
        )

    def _read_excel(self, file_path: str) -> List[str]:
        """Lê arquivo Excel e extrai itens"""
        df = pd.read_excel(file_path)

        # Encontra coluna de produtos
        possible_columns = ['Item', 'item', 'Produto', 'produto', 'Descrição', 'descrição']
        product_column = None

        for col in df.columns:
            if col in possible_columns or any(term in str(col).lower() for term in ['item', 'produto', 'descri']):
                product_column = col
                break

        if not product_column:
            product_column = df.columns[0]

        # Extrai e limpa itens
        items = []
        for _, row in df.iterrows():
            item = str(row[product_column]).strip()
            if item and item.lower() not in ['nan', 'none', '']:
                items.append(item)

        logger.info(f"📊 Extraídos {len(items)} itens da coluna '{product_column}'")
        return items

    def _optimize_item(self, item: str) -> ItemResult:
        """Otimiza um item usando IA"""

        task = Task(
            description=f"""
            Otimize esta descrição de produto para busca em e-commerce brasileiro:
            "{item}"

            Regras:
            1. Mantenha o significado original
            2. Use terminologia brasileira padrão
            3. Adicione contexto se necessário (ex: "mouse" → "mouse para computador")
            4. Padronize termos (ex: "micro ondas" → "microondas")
            5. Remova detalhes desnecessários de projeto
            6. Máximo 8 palavras

            Retorne apenas a descrição otimizada, sem explicações.
            """,
            agent=self.optimizer_agent,
            expected_output="Descrição otimizada do produto"
        )

        crew = Crew(
            agents=[self.optimizer_agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False
        )

        try:
            result = crew.kickoff()
            optimized = str(result).strip().strip('"\'')

            # Fallback: se a IA não otimizou bem, usa regras básicas
            if len(optimized) > 100 or not optimized:
                optimized = self._basic_optimization(item)
                notes = "Otimização básica aplicada"
            else:
                notes = "Otimizado por IA"

            return ItemResult(
                original=item,
                optimized=optimized,
                notes=notes
            )

        except Exception as e:
            logger.warning(f"Erro na otimização IA para '{item}': {e}")
            return ItemResult(
                original=item,
                optimized=self._basic_optimization(item),
                notes="Otimização básica (erro na IA)"
            )

    def _basic_optimization(self, item: str) -> str:
        """Otimização básica sem IA"""
        import re

        optimized = item.strip()

        # Remove frases desnecessárias
        patterns = [
            r'\(conforme.*?\)', r'conforme projeto.*', r'definid[ao] pela.*',
            r'padrão.*', r'pintura eletrostática', r'com fechadura individual'
        ]

        for pattern in patterns:
            optimized = re.sub(pattern, '', optimized, flags=re.IGNORECASE)

        # Limpa espaços
        optimized = re.sub(r'\s+', ' ', optimized).strip(' -+,.')

        # Adiciona contexto básico
        if optimized.lower() in ['mouse', 'teclado', 'monitor']:
            optimized += ' para computador'

        # Limita palavras
        words = optimized.split()
        if len(words) > 8:
            optimized = ' '.join(words[:8])

        return optimized

    def process_file(self, input_file: str, output_file: str) -> List[ItemResult]:
        """Processa arquivo Excel completo"""
        logger.info(f"🤖 Iniciando pré-processamento inteligente: {input_file}")

        # Lê itens
        items = self._read_excel(input_file)

        # Processa cada item
        results = []
        for i, item in enumerate(items):
            logger.info(f"✨ [{i+1}/{len(items)}] Otimizando: {item[:40]}...")

            result = self._optimize_item(item)
            results.append(result)

            if result.optimized != result.original:
                logger.info(f"   → {result.optimized}")

        # Salva resultados
        self._save_results(results, output_file)

        # Estatísticas
        optimized_count = sum(1 for r in results if r.optimized != r.original)
        logger.info(f"\n📊 Processamento concluído:")
        logger.info(f"   Total: {len(results)} itens")
        logger.info(f"   Otimizados: {optimized_count} ({optimized_count/len(results)*100:.1f}%)")
        logger.info(f"   Arquivo salvo: {output_file}")

        return results

    def _save_results(self, results: List[ItemResult], output_file: str):
        """Salva resultados em Excel"""
        data = []
        for result in results:
            data.append({
                'Item_Original': result.original,
                'Item_Otimizado': result.optimized,
                'Notas': result.notes
            })

        df = pd.DataFrame(data)

        # Cria arquivo com múltiplas abas
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Todos os resultados
            df.to_excel(writer, sheet_name='Resultados_Completos', index=False)

            # Apenas itens otimizados (para descoberta de preços)
            optimized_df = df[['Item_Otimizado']].copy()
            optimized_df.rename(columns={'Item_Otimizado': 'Item'}, inplace=True)
            optimized_df.to_excel(writer, sheet_name='Itens_Otimizados', index=False)

def main():
    """Função principal"""
    INPUT_FILE = os.getenv('INPUT_FILE', 'lista.xlsx')
    OUTPUT_FILE = f"Itens_Otimizados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    if not os.path.exists(INPUT_FILE):
        logger.error(f"❌ Arquivo não encontrado: {INPUT_FILE}")
        return

    try:
        processor = SmartPreprocessor()
        processor.process_file(INPUT_FILE, OUTPUT_FILE)
        logger.info("✅ Pré-processamento concluído!")

    except Exception as e:
        logger.error(f"❌ Erro no processamento: {e}")

if __name__ == "__main__":
    main()

