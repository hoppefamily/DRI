# DRI Quick Start Guide

## Installation

1. **Create virtual environment:**
   ```bash
   cd /Users/michaelhoppe/code/dri
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install DRI with dependencies:**
   ```bash
   pip install -e ".[all]"
   ```

3. **Set SEC User-Agent (required for EDGAR access):**
   ```bash
   export SEC_USER_AGENT="YourCompany your@email.com"
   ```

   Or add to `~/.bashrc` / `~/.zshrc`:
   ```bash
   echo 'export SEC_USER_AGENT="YourCompany your@email.com"' >> ~/.zshrc
   ```

## Basic Usage

### 1. Fetch 13F Data for a Manager

```bash
# Fetch recent filings for Duquesne Family Office (Stanley Druckenmiller)
dri sensor fetch 0001536411 --quarters 8 --name "Duquesne Family Office"
```

### 2. View Sensor Reading

```bash
# Show latest exposure reading
dri sensor show 0001536411

# JSON output
dri sensor show 0001536411 --format json
```

### 3. Run Full DRI Pipeline

```bash
# Compute DRI for panel (as configured in config/default_config.yaml)
dri run

# Dry run (validate without saving)
dri run --dry-run

# For specific date
dri run --date 2026-02-15
```

### 4. View DRI Regime

```bash
# Show latest snapshot
dri show

# Show history
dri history

# Since specific date
dri history --since 2025-01-01
```

## Configuration

Edit `config/default_config.yaml` to:
- Add more panel members (4-7 managers required)
- Adjust regime thresholds
- Configure decay parameters
- Set S3 bucket for storage

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=src/dri --cov-report=term-missing

# Run specific test file
pytest tests/test_sensor.py -v
```

## Next Steps

### 1. Research Panel Members

The default config has only 1 manager. You need to add 3-6 more to meet the minimum panel size of 4.

**Research candidates on SEC EDGAR:**
- https://www.sec.gov/edgar/searchedgar/companysearch

**Criteria:**
- Discretionary macro managers
- Willing to go materially risk-off
- Consistent 13F filing history
- Rates/FX/policy sensitive

**Example candidates to research:**
- Paul Tudor Jones / Tudor Investment Corp
- David Tepper / Appaloosa Management
- Bill Ackman / Pershing Square Capital
- Kyle Bass / Hayman Capital Management

**Find CIK:**
1. Search company name on EDGAR
2. Look for 13F-HR filings (quarterly)
3. Copy 10-digit CIK (e.g., 0001536411)

### 2. Update Panel Configuration

Edit `config/default_config.yaml`:

```yaml
panel:
  - cik: "0001536411"
    name: "Duquesne Family Office"
    decay_type: "tactical"
    decay_halflife_days: 30

  - cik: "YOUR_CIK_HERE"
    name: "Manager Name"
    decay_type: "structural"  # or "tactical"
    decay_halflife_days: 60   # slower decay for structural

  # Add 2-5 more...
```

### 3. Process Q4 2025 Filings

Q4 2025 13F filings are due mid-February 2026 (now!):

```bash
# Fetch for all panel members
for cik in 0001536411 YOUR_CIK_2 YOUR_CIK_3 YOUR_CIK_4; do
  dri sensor fetch $cik --quarters 8 --name "Manager Name"
done

# Run DRI pipeline
dri run

# View result
dri show
```

### 4. Deploy to AWS (Optional)

**Prerequisites:**
- AWS account with CLI configured
- GitHub repository created
- OIDC provider set up in AWS

**Steps:**

1. **Deploy infrastructure:**
   ```bash
   aws cloudformation create-stack \
     --stack-name dri-infrastructure \
     --template-body file://cloudformation-template.yaml \
     --capabilities CAPABILITY_NAMED_IAM
   ```

2. **Get outputs:**
   ```bash
   aws cloudformation describe-stacks \
     --stack-name dri-infrastructure \
     --query 'Stacks[0].Outputs'
   ```

3. **Add GitHub secrets:**
   - `AWS_ROLE_ARN`: From CloudFormation output
   - `S3_BUCKET`: From CloudFormation output
   - `SEC_USER_AGENT`: Your contact info

4. **Push to GitHub:**
   ```bash
   git remote add origin git@github.com:hoppefamily/dri.git
   git push -u origin main
   ```

5. **Workflow runs monthly automatically** (20th of each month)

## Troubleshooting

### "SEC User-Agent is required"
Set the environment variable:
```bash
export SEC_USER_AGENT="YourCompany your@email.com"
```

### "Insufficient panel members"
You need at least 4 managers in your panel. Edit `config/default_config.yaml` and add more CIKs.

### "Failed to fetch filings"
- Check CIK is correct (10 digits with leading zeros)
- Verify SEC EDGAR is accessible
- Check rate limiting (10 req/sec max)
- Ensure User-Agent is set correctly

### Tests failing
Some tests require fixtures. Ensure you're in the project root:
```bash
cd /Users/michaelhoppe/code/dri
pytest tests/ -v
```

## Project Structure

```
dri/
├── src/dri/          # Main package
│   ├── edgar.py      # SEC EDGAR fetcher
│   ├── sensor.py     # Single-manager exposure
│   ├── aggregator.py # Multi-manager metrics
│   ├── regime.py     # Regime classification
│   ├── pipeline.py   # Orchestrator
│   └── cli.py        # Command-line interface
├── tests/            # Test suite
├── config/           # Configuration
└── docs/             # Documentation
```

## Documentation

- **[README.md](README.md)** — Overview and architecture
- **[PHILOSOPHY.md](PHILOSOPHY.md)** — Design rationale and limitations
- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** — Detailed technical plan

## Support

For issues or questions:
1. Check [PHILOSOPHY.md](PHILOSOPHY.md) for design rationale
2. Review test cases in `tests/` for usage examples
3. Inspect `config/default_config.yaml` for all options
4. Reference the DRI specification in `/Users/michaelhoppe/DRI/`
