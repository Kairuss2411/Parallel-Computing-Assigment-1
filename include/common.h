#pragma once

#include <cstdlib>
#include <iostream>
#include <string>
#include <string_view>

// Parse command-line arguments in --key=value form.
// Example: --threads=8
inline std::string get_str_arg(int argc, char** argv,
                               const std::string& key,
                               const std::string& default_value) {
    const std::string prefix = "--" + key + "=";
    for (int i = 1; i < argc; ++i) {
        const std::string arg(argv[i]);
        if (arg.rfind(prefix, 0) == 0) return arg.substr(prefix.size());
    }
    return default_value;
}

inline int get_int_arg(int argc, char** argv,
                       const std::string& key,
                       int default_value) {
    const std::string value = get_str_arg(argc, argv, key, "");
    if (value.empty()) return default_value;

    char* end = nullptr;
    const long parsed = std::strtol(value.c_str(), &end, 10);
    if (end == value.c_str() || *end != '\0' ||
        parsed < -2147483647L - 1L || parsed > 2147483647L) {
        std::cerr << "Invalid integer for --" << key << ": " << value << '\n';
        std::exit(2);
    }
    return static_cast<int>(parsed);
}

// CSV columns: platform,task,algorithm,threads,outside_work,metric,value,rep
inline void csv_row(const std::string& platform, int task,
                    const std::string& algorithm, int threads,
                    int outside_work, const std::string& metric,
                    double value, int rep) {
    std::cout << platform << ','
              << task << ','
              << algorithm << ','
              << threads << ','
              << outside_work << ','
              << metric << ','
              << value << ','
              << rep << '\n';
}
