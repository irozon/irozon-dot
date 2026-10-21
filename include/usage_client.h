#pragma once
#include "usage.h"

namespace usage_client {
bool configured();
void fetch();
usage::Snapshot snapshot();
usage::Status status();
}  // namespace usage_client
