#pragma once
// Umbrella header: include all lock implementations (matches the
// `#include "lock.h"` used by the assignment template).

#include "common.h"

#include "lock_tas.h"
#include "lock_ttas.h"
#include "lock_mcs.h"
#include "lock_baseline.h"
