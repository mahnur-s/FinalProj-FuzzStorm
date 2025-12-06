#include <iostream>
#include <string>
#include <memory>
#include <jsoncpp/json/json.h>
int main() {
    // Set up the modern JsonCpp parser
    Json::CharReaderBuilder builder;
    char A,B;
    std::cin.get(A);
    std::cin.get(B);
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

        Json::Value root;
        std::string errs;

        std::unique_ptr<Json::CharReader> reader(builder.newCharReader());
        
        bool ok = reader->parse(
            line.c_str(),
            line.c_str() + line.size(),
            &root,
            &errs
        );

        if (ok) {
            // For fuzzing you might comment this out to keep output minimal
            std::cout << "OK\n";
        } else {
            std::cout << "ERR: " << errs << "\n";
        }
    }

    return 0;
}