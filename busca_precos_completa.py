#!/usr/bin/env python3
"""
Intelligent Price Discovery System with CrewAI Preprocessing
Combines agent-based preprocessing with price discovery for optimal results.
"""

import os
import sys
import subprocess
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntelligentPriceDiscoverySystem:
    """Integrated system with CrewAI preprocessing and price discovery"""
    
    def __init__(self):
        """Initialize the integrated system"""
        self.input_file = os.getenv('INPUT_FILE', 'lista.xlsx')
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # File paths
        self.preprocessed_file = f"Preprocessed_Items_{self.timestamp}.xlsx"
        self.final_results_file = f"Intelligent_Price_Discovery_Results_{self.timestamp}.xlsx"
        
        # Check required API keys
        self._check_api_keys()
    
    def _check_api_keys(self):
        """Check if required API keys are available"""
        openai_key = os.getenv('OPENAI_API_KEY')
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        
        if not openai_key:
            logger.error("❌ OPENAI_API_KEY not found in environment variables")
            logger.info("Required for CrewAI agents. Please add to .env file.")
            sys.exit(1)
        
        if not perplexity_key:
            logger.error("❌ PERPLEXITY_API_KEY not found in environment variables")
            logger.info("Required for price discovery. Please add to .env file.")
            sys.exit(1)
        
        logger.info("✅ API keys found and ready")
    
    def run_preprocessing(self) -> bool:
        """Run CrewAI preprocessing step"""
        logger.info("🤖 STEP 1: Running CrewAI Agent Preprocessing")
        logger.info("=" * 60)
        
        try:
            # Import and run preprocessing
            from preprocessamento import SmartPreprocessor

            processor = SmartPreprocessor()
            results = processor.process_file(self.input_file, self.preprocessed_file)

            if not results:
                logger.error("❌ Preprocessing failed - no results generated")
                return False

            logger.info(f"✅ Preprocessing complete: {len(results)} items optimized")
            return True
            
        except ImportError as e:
            logger.error(f"❌ CrewAI dependencies not installed: {e}")
            logger.info("Please install: pip install crewai langchain-openai")
            return False
        except Exception as e:
            logger.error(f"❌ Preprocessing failed: {e}")
            return False
    
    def run_price_discovery(self) -> bool:
        """Run price discovery on preprocessed items"""
        logger.info("\n💰 STEP 2: Running Price Discovery")
        logger.info("=" * 60)
        
        try:
            # Check if preprocessed file exists
            if not os.path.exists(self.preprocessed_file):
                logger.error(f"❌ Preprocessed file not found: {self.preprocessed_file}")
                return False
            
            # Read the optimized items sheet
            searchable_df = pd.read_excel(self.preprocessed_file, sheet_name='Itens_Otimizados')
            
            if len(searchable_df) == 0:
                logger.warning("⚠️ No searchable items in preprocessed file")
                return False
            
            logger.info(f"📊 Processing {len(searchable_df)} optimized items...")
            
            # Import and run price discovery
            from busca_precos_basica import PriceDiscoverySystem
            
            # Get API key
            api_key = str(os.getenv('PERPLEXITY_API_KEY'))
            
            # Initialize price discovery system
            price_system = PriceDiscoverySystem(api_key)
            
            # Process each optimized item
            results = []
            found_count = 0
            
            for idx, (_, row) in enumerate(searchable_df.iterrows()):
                item = row['Item']

                logger.info(f"🔍 [{idx+1}/{len(searchable_df)}] Searching: {item[:50]}...")

                # Process the item
                result = price_system.process_item(item)
                results.append(result)

                # Log result
                if result.status == 'price_found':
                    found_count += 1
                    logger.info(f"✅ [{idx+1}] FOUND: R$ {result.price:.2f} - {result.store}")
                elif result.status == 'filtered_out':
                    logger.info(f"⚠️ [{idx+1}] FILTERED: {result.reason}")
                else:
                    logger.info(f"❌ [{idx+1}] NOT FOUND: {result.reason}")
                
                # Rate limiting
                import time
                time.sleep(3)
            
            # Save price discovery results
            price_results_file = f"Price_Results_{self.timestamp}.xlsx"
            price_system._save_results(results, price_results_file)
            
            logger.info(f"💾 Price discovery results saved to: {price_results_file}")
            logger.info(f"🎯 Success rate: {found_count}/{len(results)} ({found_count/len(results)*100:.1f}%)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Price discovery failed: {e}")
            return False
    
    def create_final_report(self) -> bool:
        """Create comprehensive final report combining all results"""
        logger.info("\n📊 STEP 3: Creating Final Comprehensive Report")
        logger.info("=" * 60)
        
        try:
            # Load all data files
            preprocessed_df = pd.read_excel(self.preprocessed_file, sheet_name='Resultados_Completos')
            price_results_file = f"Price_Results_{self.timestamp}.xlsx"
            
            if os.path.exists(price_results_file):
                price_df = pd.read_excel(price_results_file)
            else:
                logger.warning("⚠️ Price results file not found, creating report without prices")
                price_df = pd.DataFrame()
            
            # Merge preprocessing and price data
            if not price_df.empty:
                # Create mapping from optimized items to price results
                price_mapping = {}
                for _, row in price_df.iterrows():
                    price_mapping[row['Item']] = {
                        'Price_Status': row['Status'],
                        'Price_Reason': row['Reason'],
                        'Price': row['Price'],
                        'Store': row['Store'],
                        'URL': row['URL'],
                        'Confidence': row['Confidence']
                    }
                
                # Add price information to preprocessed data
                for col in ['Price_Status', 'Price_Reason', 'Price', 'Store', 'URL', 'Confidence']:
                    preprocessed_df[col] = None
                
                for idx, row in preprocessed_df.iterrows():
                    if row['Is_Searchable'] and row['Optimized_Item'] in price_mapping:
                        price_info = price_mapping[row['Optimized_Item']]
                        for col, value in price_info.items():
                            preprocessed_df.at[idx, col] = value
                    elif not row['Is_Searchable']:
                        preprocessed_df.at[idx, 'Price_Status'] = 'filtered_out'
                        preprocessed_df.at[idx, 'Price_Reason'] = 'Filtered during preprocessing'
            
            # Create comprehensive Excel report
            with pd.ExcelWriter(self.final_results_file, engine='openpyxl') as writer:
                # Main comprehensive results
                preprocessed_df.to_excel(writer, sheet_name='Complete_Results', index=False)
                
                # Summary statistics
                total_items = len(preprocessed_df)
                searchable_items = len(preprocessed_df[preprocessed_df['Is_Searchable'] == True])
                filtered_items = total_items - searchable_items
                
                if not price_df.empty:
                    found_items = len(preprocessed_df[preprocessed_df['Price_Status'] == 'price_found'])
                    not_found_items = len(preprocessed_df[preprocessed_df['Price_Status'] == 'not_found'])
                else:
                    found_items = 0
                    not_found_items = 0
                
                summary_data = {
                    'Metric': [
                        'Total Items',
                        'Searchable Items (after AI preprocessing)',
                        'Filtered Items (by AI agents)',
                        'Prices Found',
                        'Prices Not Found',
                        'Preprocessing Success Rate (%)',
                        'Price Discovery Success Rate (%)',
                        'Overall Success Rate (%)'
                    ],
                    'Value': [
                        total_items,
                        searchable_items,
                        filtered_items,
                        found_items,
                        not_found_items,
                        f"{searchable_items/total_items*100:.1f}%" if total_items > 0 else "0%",
                        f"{found_items/searchable_items*100:.1f}%" if searchable_items > 0 else "0%",
                        f"{found_items/total_items*100:.1f}%" if total_items > 0 else "0%"
                    ]
                }
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Items with prices found
                if found_items > 0:
                    found_df = preprocessed_df[preprocessed_df['Price_Status'] == 'price_found']
                    found_df.to_excel(writer, sheet_name='Prices_Found', index=False)
                
                # Filtered items
                if filtered_items > 0:
                    filtered_df = preprocessed_df[preprocessed_df['Is_Searchable'] == False]
                    filtered_df.to_excel(writer, sheet_name='Filtered_Items', index=False)
            
            logger.info(f"📋 Final comprehensive report created: {self.final_results_file}")
            
            # Print final summary
            logger.info("\n" + "="*60)
            logger.info("🎯 INTELLIGENT PRICE DISCOVERY - FINAL RESULTS")
            logger.info("="*60)
            logger.info(f"📊 Total items processed: {total_items}")
            logger.info(f"🤖 AI preprocessing success: {searchable_items}/{total_items} ({searchable_items/total_items*100:.1f}%)")
            logger.info(f"💰 Price discovery success: {found_items}/{searchable_items} ({found_items/searchable_items*100:.1f}%)" if searchable_items > 0 else "💰 Price discovery: No searchable items")
            logger.info(f"🎯 Overall success rate: {found_items}/{total_items} ({found_items/total_items*100:.1f}%)")
            logger.info("="*60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create final report: {e}")
            return False
    
    def run_complete_workflow(self):
        """Run the complete intelligent price discovery workflow"""
        logger.info("🚀 INTELLIGENT PRICE DISCOVERY SYSTEM")
        logger.info("Powered by CrewAI Agents + Perplexity AI")
        logger.info("="*60)
        
        start_time = datetime.now()
        
        # Step 1: Preprocessing
        if not self.run_preprocessing():
            logger.error("❌ Workflow failed at preprocessing step")
            return
        
        # Step 2: Price Discovery
        if not self.run_price_discovery():
            logger.error("❌ Workflow failed at price discovery step")
            return
        
        # Step 3: Final Report
        if not self.create_final_report():
            logger.error("❌ Workflow failed at report generation step")
            return
        
        # Calculate total time
        end_time = datetime.now()
        total_time = end_time - start_time
        
        logger.info(f"\n🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
        logger.info(f"⏱️ Total processing time: {total_time}")
        logger.info(f"📁 Final report: {self.final_results_file}")

def main():
    """Main function to run intelligent price discovery"""
    
    # Check if input file exists
    input_file = os.getenv('INPUT_FILE', 'lista.xlsx')
    if not os.path.exists(input_file):
        logger.error(f"❌ Input file not found: {input_file}")
        logger.info("Please ensure the Excel file is in the same directory.")
        return
    
    try:
        system = IntelligentPriceDiscoverySystem()
        system.run_complete_workflow()
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Workflow interrupted by user")
    except Exception as e:
        logger.error(f"❌ Workflow failed: {e}")

if __name__ == "__main__":
    main()
