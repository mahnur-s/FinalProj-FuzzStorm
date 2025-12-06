#include <iostream>
#include <string>
#include <memory>
#include <cstdint>
#include <jsoncpp/json/json.h>

class JsonEncoder {
public:
    JsonEncoder(const uint8_t *data, size_t size)
        : data_(data), size_(size), pos_(0), depth_(0), nodeCount_(0) {}

    std::string encode() {
        out_.clear();
        depth_ = 0;
        nodeCount_ = 0;
        emitValue();              // emit exactly one JSON value
        return out_;
    }

private:
    static constexpr size_t kMaxDepth = 8;
    static constexpr size_t kMaxNodes = 1024;

    const uint8_t *data_;
    size_t size_;
    size_t pos_;
    int depth_;
    size_t nodeCount_;
    std::string out_;

    // 25 general tokens:
    //  - 0..2   : false, true, null
    //  - 3..16  : string literals
    //  - 17..22 : numbers
    //  - 23     : array ([...])
    //  - 24     : object ({...})
    static constexpr size_t kNumGeneralTokens = 25;

    // 14 string tokens for keys
    static constexpr size_t kNumStringTokens = 14;

    uint8_t nextByte() {
        if (pos_ >= size_) {
            return 0; // default when out of data
        }
        return data_[pos_++];
    }

    // Emit one of the allowed string literals by index 0..13
    void emitStringByIndex(size_t idx) {
        switch (idx) {
            case 0:  out_ += "\"a\""; break;
            case 1:  out_ += "\"A\""; break;
            case 2:  out_ += "\"!\""; break;
            case 3:  out_ += "\"\\\"\""; break;       // string containing a double quote: "\""
            case 4:  out_ += "\"'\""; break;          // single quote
            case 5:  out_ += "\"0\""; break;
            case 6:  out_ += "\"Cool1\""; break;
            case 7:  out_ += "\"2Cool!\""; break;
            case 8:  out_ += "\"!Yay?\""; break;
            case 9:  out_ += "\"\\b\""; break;        // backspace escape
            case 10: out_ += "\"\\r\""; break;        // carriage return escape
            case 11: out_ += "\"\\u0000\""; break;    // explicit null char
            case 12: out_ += "\"\\n\""; break;        // newline escape (NOT raw 0x0A)
            case 13: out_ += "\" \""; break;          // space inside string
            default: out_ += "\"a\""; break;
        }
    }

    void emitValue() {
        if (depth_ >= static_cast<int>(kMaxDepth) || nodeCount_ >= kMaxNodes) {
            out_ += "null";
            return;
        }
        ++nodeCount_;

        uint8_t b = nextByte();

        // upper 5 bits → token kind index (0..31)
        uint8_t kindBits  = b >> 3;                         // 0..31
        size_t tokenIndex = kindBits % kNumGeneralTokens;   // 0..24

        // lower 3 bits → size (0..7) for arrays/objects
        unsigned sizeBits = b & 0x07;

        switch (tokenIndex) {
            // booleans / null
            case 0: out_ += "false"; break;
            case 1: out_ += "true";  break;
            case 2: out_ += "null";  break;

            // string literals (same set as key strings)
            case 3:  emitStringByIndex(0);  break;
            case 4:  emitStringByIndex(1);  break;
            case 5:  emitStringByIndex(2);  break;
            case 6:  emitStringByIndex(3);  break;
            case 7:  emitStringByIndex(4);  break;
            case 8:  emitStringByIndex(5);  break;
            case 9:  emitStringByIndex(6);  break;
            case 10: emitStringByIndex(7);  break;
            case 11: emitStringByIndex(8);  break;
            case 12: emitStringByIndex(9);  break;
            case 13: emitStringByIndex(10); break;
            case 14: emitStringByIndex(11); break;
            case 15: emitStringByIndex(12); break;
            case 16: emitStringByIndex(13); break;

            // numbers
            case 17: out_ += "0";   break;
            case 18: out_ += "1";   break;
            case 19: out_ += "-1";  break;
            case 20: out_ += "+0";  break;   // if JsonCpp rejects +0 as number, turn this into "\"+0\"" instead
            case 21: out_ += "-0";  break;
            case 22: out_ += "+3";  break;   // same note as +0

            // array
            case 23:
                emitArray(sizeBits);   // 0..7 elements
                break;

            // object
            case 24:
                emitObject(sizeBits);  // 0..7 fields
                break;

            default:
                out_ += "null";
                break;
        }
    }

    void emitArray(unsigned count) {
        if (depth_ >= static_cast<int>(kMaxDepth)) {
            out_ += "null";
            return;
        }
        out_ += '[';
        ++depth_;
        for (unsigned i = 0; i < count; ++i) {
            if (i > 0) out_ += ',';
            emitValue();
        }
        --depth_;
        out_ += ']';
    }

    void emitObject(unsigned count) {
        if (depth_ >= static_cast<int>(kMaxDepth)) {
            out_ += "null";
            return;
        }
        out_ += '{';
        ++depth_;
        for (unsigned i = 0; i < count; ++i) {
            if (i > 0) out_ += ',';
            emitKey();              // key must be a string
            out_ += ':';
            emitValue();            // value: any general token
        }
        --depth_;
        out_ += '}';
    }

    void emitKey() {
        uint8_t b = nextByte();
        size_t idx = static_cast<size_t>(b) % kNumStringTokens;
        emitStringByIndex(idx);
    }
};

// Your line-based harness, now using JsonEncoder on each line.
int main() {
    // Set up the modern JsonCpp parser
    Json::CharReaderBuilder builder;
    char A,B;
    std::cin.get(A);
    std::cin.get(B);
    std::cout << A << B;
builder["collectComments"] = A & 0x1;
builder["allowComments"] = A & 0x2;
builder["allowTrailingCommas"] = A & 0x4;
builder["strictRoot"] = A & 0x8;
builder["allowDroppedNullPlaceholders"] = A & 0x10;
builder["allowNumericKeys"] = A & 0x20;
builder["allowSingleQuotes"] = A & 0x40;
builder["failIfExtra"] = A & 0x80;
builder["rejectDupKeys"] = B & 0x1;
builder["allowSpecialFloats"] = B & 0x2;
builder["skipBom"] = B & 0x4;
    std::string line;

    while (std::getline(std::cin, line)) {
        // Skip empty lines (optional)
        if (line.empty())
            continue;

        // Treat the line bytes as input *to the encoder*, not as JSON yet.
        const uint8_t *data = reinterpret_cast<const uint8_t *>(line.data());
        JsonEncoder enc(data, line.size());
        std::string json = enc.encode();  // always syntactically valid (per our design)
        std::cout << json << "\n";      // optionally print the generated JSON
        Json::Value root;
        std::string errs;

        std::unique_ptr<Json::CharReader> reader(builder.newCharReader());

        bool ok = reader->parse(
            json.c_str(),
            json.c_str() + json.size(),
            &root,
            &errs
        );

        if (ok) {
            //std::cout << "OK\n";
        } else {
            //std::cout << "ERR: " << errs << "\n";
        }
    }

    return 0;
}
