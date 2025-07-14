import pandas as pd
import requests
import json
import time
import logging
import os
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class PriceResult:
    """Result of price search for a single item"""
    item: str
    status: str  # 'price_found', 'filtered_out', 'not_found'
    reason: str
    price: Optional[float] = None
    store: Optional[str] = None
    url: Optional[str] = None
    confidence: Optional[float] = None

class PriceDiscoverySystem:
    """
    Complete price discovery system with integrated validation and search.
    Single responsibility: Process Excel file and return price results.
    """
    
    # Validation rules - centralized in the main class
    GENERIC_TERMS = [
        'materiais de escritório', 'serviços gerais', 'comunicação visual',
        'paisagismo', 'instalação', 'montagem', 'serviços de', 'mão de obra',
        'consultoria', 'projeto', 'planejamento', 'diversos', 'variados',
        'conforme', 'definida pela', 'padrão', 'geral', 'acabamento',
        'revestimento', 'pintura', 'elétrica', 'hidráulica', 'estrutural'
    ]
    
    SERVICE_TERMS = [
        'serviços', 'instalação', 'montagem', 'manutenção', 'consultoria',
        'projeto', 'planejamento', 'execução', 'reforma', 'construção',
        'adequação', 'regularização', 'licenciamento', 'aprovação'
    ]
    
    SPECIFIC_INDICATORS = [
        # Brands
        'dell', 'hp', 'samsung', 'lg', 'brastemp', 'electrolux', 'consul',
        'philips', 'panasonic', 'sony', 'apple', 'microsoft', 'logitech',
        'daikin', 'springer', 'midea', 'gree', 'carrier', 'york',
        # Product types
        'notebook', 'laptop', 'desktop', 'monitor', 'impressora', 'scanner',
        'smartphone', 'tablet', 'iphone', 'ipad', 'galaxy', 'mouse', 'teclado',
        'geladeira', 'freezer', 'fogão', 'cooktop', 'forno', 'microondas',
        'liquidificador', 'batedeira', 'cafeteira', 'torradeira', 'sanduicheira',
        'ar condicionado', 'ventilador', 'aquecedor', 'purificador',
        'televisão', 'tv', 'soundbar', 'home theater', 'caixa de som',
        # Measurements/specs
        'polegadas', 'litros', 'watts', 'btus', 'rpm', 'ghz', 'gb', 'tb',
        'full hd', '4k', 'led', 'oled', 'smart', 'inverter', 'digital',
        # Furniture
        'cadeira', 'mesa', 'armário', 'estante', 'roupeiro', 'gaveteiro',
        'balcão', 'bancada', 'prateleira', 'rack', 'painel', 'sofá'
    ]
    
    def __init__(self, api_key: str):
        """Initialize with Perplexity API key"""
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _is_searchable(self, item_description: str) -> bool:
        """
        Validate if item is searchable (integrated validation).
        Single responsibility: determine searchability.
        """
        if not item_description or len(item_description.strip()) < 5:
            return False
        
        item_lower = item_description.lower().strip()
        
        # Check for generic terms
        for term in self.GENERIC_TERMS:
            if term in item_lower:
                return False
        
        # Check for service terms
        for term in self.SERVICE_TERMS:
            if item_lower.startswith(term) or f" {term}" in item_lower:
                return False
        
        # Must have meaningful words
        meaningful_words = [
            word for word in item_lower.split() 
            if len(word) > 2 and word not in ['de', 'da', 'do', 'para', 'com', 'em', 'na', 'no']
        ]
        
        if len(meaningful_words) < 2:
            return False
        
        # Check for specific indicators
        specific_count = sum(1 for indicator in self.SPECIFIC_INDICATORS if indicator in item_lower)
        
        return specific_count >= 1 or self._has_product_patterns(item_lower)
    
    def _has_product_patterns(self, item_lower: str) -> bool:
        """Check for product-like patterns"""
        # Has measurements or specifications
        if re.search(r'\d+\s*(cm|mm|m|polegadas|litros|watts|btus|gb|tb|kg)', item_lower):
            return True
        # Has model numbers
        if re.search(r'[a-z]+\d+|modelo\s+\w+|\w+\s*-\s*\d+', item_lower):
            return True
        # Has colors or materials
        descriptors = ['branco', 'preto', 'azul', 'inox', 'aço', 'madeira', 'plástico']
        return any(desc in item_lower for desc in descriptors)
    
    def _simplify_item_name(self, item_description: str) -> str:
        """Simplifica o nome do item para melhorar os resultados da pesquisa"""
        simplified = item_description
        
        # Remove unnecessary phrases
        remove_patterns = [
            r'\(conforme.*?\)', r'\(definid[ao].*?\)', r'conforme projeto.*',
            r'definid[ao] pela.*', r'padrão.*', r'dimensões?:?\s*\d+.*',
            r'pintura eletrostática', r'com fechadura individual'
        ]
        
        for pattern in remove_patterns:
            simplified = re.sub(pattern, '', simplified, flags=re.IGNORECASE)
        
        # Clean up
        simplified = re.sub(r'\s+', ' ', simplified).strip(' -+,.')
        
        # Limit length
        words = simplified.split()
        if len(words) > 8:
            simplified = ' '.join(words[:8])
        
        return simplified
    
    def _search_with_ai(self, item_description: str) -> Optional[Dict[str, Any]]:
        """
        Pesquisa o preço de um item usando a IA da Perplexity.
        """
        simplified_item = self._simplify_item_name(item_description)
        
        prompt = f"""
        Encontre o menor preço atual de "{simplified_item}" no Brasil.
        
        Requisitos:
        - Busque apenas em sites brasileiros de e-commerce
        - Retorne apenas se encontrar um preço específico e confiável
        - Formato da resposta: JSON com price (número), store (nome da loja), url (link), confidence (0-1)
        
        Exemplo: {{"price": 299.90, "store": "Mercado Livre", "url": "https://...", "confidence": 0.95}}
        """
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                return self._extract_price_data(content)
            else:
                logger.error(f"Perplexity API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Pesquisa com IA falhou: {e}")
            return None
    
    def _extract_price_data(self, ai_response: str) -> Optional[Dict[str, Any]]:
        """Extrai dados estruturados do preço da resposta da IA"""
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[^}]*"price"[^}]*\}', ai_response)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data.get('price'), (int, float)) and data['price'] > 0:
                    return data
        except:
            pass
        
        # Fallback: extract price with regex
        price_match = re.search(r'R\$\s*(\d+(?:[.,]\d+)*)', ai_response)
        if price_match:
            price_str = price_match.group(1).replace(',', '.')
            try:
                price = float(price_str)
                if 5.0 <= price <= 100000.0:
                    return {
                        "price": price,
                        "store": "Mercado Livre",
                        "url": "https://mercadolivre.com.br",
                        "confidence": 0.5
                    }
            except:
                pass
        
        return None
    
    def process_item(self, item_description: str) -> PriceResult:
        """
        Processa um único item, incluindo validação e busca de preço
        """
        # Step 1: Validate
        if not self._is_searchable(item_description):
            return PriceResult(
                item=item_description,
                status="filtrado",
                reason="Item muito genérico ou não pesquisável"
            )
        
        # Step 2: Search with AI
        logger.info(f"🤖 Searching: {item_description[:50]}...")
        price_data = self._search_with_ai(item_description)
        
        if price_data:
            return PriceResult(
                item=item_description,
                status="price_found",
                reason="Found via AI search",
                price=price_data.get('price'),
                store=price_data.get('store'),
                url=price_data.get('url'),
                confidence=price_data.get('confidence', 0.8)
            )
        else:
            return PriceResult(
                item=item_description,
                status="não encontrado",
                reason="Nenhuma correspondência encontrada"
            )
    
    def process_excel_file(self, input_file: str, output_file: str) -> List[PriceResult]:
        """
        Processa uma planilha Excel completa
        """
        logger.info(f"📂 Loading Excel file: {input_file}")
        
        try:
            df = pd.read_excel(input_file)
        except Exception as e:
            logger.error(f"Falha ao carregar arquivo Excel: {e}")
            return []
        
        logger.info(f"🔢 Processando {len(df)} itens...")
        
        results = []
        found_count = 0
        filtered_count = 0
        
        for i, (_, row) in enumerate(df.iterrows()):
            item = row.get('Item', 'N/A')
            
            # Process item
            result = self.process_item(item)
            results.append(result)
            
            # Log result
            if result.status == 'price_found':
                found_count += 1
                logger.info(f"✅ [{i+1}] FOUND: R$ {result.price:.2f} - {result.store}")
            elif result.status == 'filtered_out':
                filtered_count += 1
                logger.info(f"⚠️ [{i+1}] FILTERED: {result.reason}")
            else:
                logger.info(f"❌ [{i+1}] NOT FOUND: {result.reason}")
            
            # Rate limiting
            time.sleep(1.5)
        
        # Save results
        self._save_results(results, output_file)
        
        # Print summary
        total = len(results)
        logger.info(f"\n📊 SUMMARY: {found_count} found, {filtered_count} filtered, {total-found_count-filtered_count} not found")
        logger.info(f"🎯 Success rate: {found_count/total*100:.1f}% of total items")
        logger.info(f"⚡ Efficiency: {filtered_count} items saved from API calls")
        
        return results
    
    def _save_results(self, results: List[PriceResult], output_file: str):
        """Save results to Excel file"""
        data = []
        for result in results:
            data.append({
                'Item': result.item,
                'Status': result.status,
                'Reason': result.reason,
                'Price': result.price,
                'Store': result.store,
                'URL': result.url,
                'Confidence': result.confidence
            })
        
        df = pd.DataFrame(data)
        df.to_excel(output_file, index=False)
        logger.info(f"💾 Results saved to: {output_file}")

def main():
    """Função principal para execução do sistema"""
    
    # Configuration
    INPUT_FILE = os.getenv('INPUT_FILE', 'lista.xlsx')
    OUTPUT_FILE = f"Resultado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # Get API key
    api_key = str(os.getenv('PERPLEXITY_API_KEY'))

    # Check input file
    if not os.path.exists(INPUT_FILE):
        logger.error(f"❌ Input file not found: {INPUT_FILE}")
        return
    
    # Run system
    logger.info("🚀 Starting Price Discovery System")
    logger.info("Strategy: Integrated validation + AI search")
    
    try:
        system = PriceDiscoverySystem(api_key)
        results = system.process_excel_file(INPUT_FILE, OUTPUT_FILE)
        logger.info(f"Results: {results}")
        logger.info("✅ Processing complete!")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Processing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")

if __name__ == "__main__":
    main()
