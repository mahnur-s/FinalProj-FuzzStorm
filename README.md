# Example Usages

### Run Plotter

python3 plot_coverage_fast.py \
  --runs out2:out3 \
  --labels "Default Fuzzer":"Encoded-based Fuzzing" \
  --time-shifts 0:60 \
  --output coverage_comparison_out2_vs_out3_seed420.png \
  --harness ./jsoncpp_fuzz_cov

## Check Coverage
### Note: Modify hardcoded paths inside the script.

./coverage.sh

### Compilation with AFL-fast

afl-clang-fast++ -O2 main.cpp \
  -Ijsoncpp/include \
  jsoncpp/build-afl/lib/libjsoncpp.a \
  -o jsoncpp_fuzz

## Generate Seeds from Interesting Inputs Found by AFL++
### Note: Modify paths inside the script.

python3 seed.py

### Example Usage of AFL++

afl-fuzz \
  -i intrim \
  -o out3 \
  -x json.dict \
  -s 67 \
  -V 1800 \
  -D \
  -- ./jsoncpp_fuzz

# Notes
### Use AFL++ trim functions to optimize generated seeds.
