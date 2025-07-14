# 🚀 Quick Start Guide

## ⚡ 5-Minute Setup

### 1. **Clone & Install**

```bash
git clone https://github.com/XSirch/lista-de-compras
cd price-discovery-system
pip install -r requirements.txt
```

### 2. **Configure API Key**

```bash
# Copy example config
cp .env.example .env

# Edit .env and add your Perplexity API key
PERPLEXITY_API_KEY=pplx-your-key-here
```

### 3. **Prepare Your Data**

- Place your Excel file in the project directory
- Rename it to: `Lista_Compras_Enxoval_Agile_Categorizada.xlsx`
- Ensure it has a column named "Item" with product descriptions

### 4. **Run the System**

```bash
python price_discovery.py
```

## 📊 What Happens Next

**Single integrated process** (2-5 minutes):

1. **🔍 Auto-validation** - Filters searchable items inline
2. **🤖 AI Search** - Searches for prices using Perplexity AI
3. **📋 Results** - Creates `Price_Discovery_Results_YYYYMMDD_HHMMSS.xlsx`

## 🎯 Expected Results

- **Success Rate**: 40-70% of searchable items
- **Confidence**: 80-95% on found items
- **Sources**: Brazilian e-commerce sites
- **Cost**: ~$0.01 per item searched

## ❓ Need Help?

- Check `README.md` for detailed documentation
- Verify your API key in `.env` file
- Ensure Excel file has "Item" column
- Check logs for specific error messages

## 🎉 Success!

When complete, you'll have:

- ✅ Single comprehensive results file
- ✅ All items processed (found/filtered/not found)
- ✅ Cost and efficiency metrics in logs
- ✅ Clean, maintainable codebase
