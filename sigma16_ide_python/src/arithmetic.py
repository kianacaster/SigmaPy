# arithmetic.py

# Copyright (C) 2024 John T. O'Donnell. License: GNU GPL Version 3
# See Sigma16/README, LICENSE, and https://jtod.github.io/home/Sigma16

# This file is part of Sigma16. Sigma16 is free software: you can
# redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
# Sigma16 is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details. You should have received
# a copy of the GNU General Public License along with Sigma16. If
# not, see <https://www.gnu.org/licenses/>.

# ------------------------------------------------------------------------
# arithmetic.py defines arithmetic for the architecture using
# Python arithmetic. This includes word representation, data
# conversions, and bit manipulation, operations on fields, and
# arithmetic as required by the instruction set architecture.
# ------------------------------------------------------------------------

import common
import architecture as arch

word16mask = 0x0000FFFF
word32mask = 0xFFFFFFFF

# ------------------------------------------------------------------------
# Ensuring and asserting validity of words
# ------------------------------------------------------------------------

# All operations that produce a word should produce a valid word,
# which is represented as a nonnegative integer. For a k-bit word,
# the value x must satisfy 0 <= x < 2^k. The assert functions check
# a value and output an error message to the console if it is not
# valid.

# Addresses are limited to either 16 bits for S16 or 32 bits for S32.
# If an address exceeds this range it wraps around. This is
# implemented by anding its value with addressMask.

def limit16(x):
    return x & word16mask

def limit32(x):
    return x & word32mask

def assert16(x):
    if 0 <= x < 2**16:
        return x
    else:
        common.indicate_error(f"assert16 fail: {x}")
        return x & 0x0000FFFF

def assert32(x):
    if 0 <= x < 2**32:
        return x
    else:
        common.indicate_error(f"assert32 fail: {x}")
        return x & 0xFFFFFFFF

def assert64(x):
    return x

def truncate_word(x):
    r = x & 0xFFFF
    common.mode.devlog(f"truncate_word x{word_to_hex4(x)} r={word_to_hex4(r)}")
    return r

def truncate_word32(x):
    r = x & 0xFFFFFFFF
    return r

# ------------------------------------------------------------------------
# Logic
# ------------------------------------------------------------------------

def logic_function(mnemonic):
    if mnemonic == "andnew" or mnemonic == "and":
        return 1
    elif mnemonic == "ornew" or mnemonic == "or":
        return 7
    elif mnemonic == "xornew" or mnemonic == "xor":
        return 6
    elif mnemonic == "invnew" or mnemonic == "inv":
        return 12
    else:
        return 0

def apply_logic_fcn_bit(fcn, x, y):
    if x == 0:
        result = arch.get_bit_in_word_le(fcn, 3) if y == 0 else arch.get_bit_in_word_le(fcn, 2)
    else:
        result = arch.get_bit_in_word_le(fcn, 1) if y == 0 else arch.get_bit_in_word_le(fcn, 0)
    common.mode.devlog(f"apply_logic_fcn fcn={fcn} x={x} y={y} result={result}")
    return result

def lut(p, q, r, s, x, y):
    return p if x == 0 and y == 0 else q if x == 0 else r if y == 0 else s

def apply_logic_fcn_field(fcn, x, y, idx1, idx2):
    p = arch.get_bit_in_word_le(fcn, 3)
    q = arch.get_bit_in_word_le(fcn, 2)
    r = arch.get_bit_in_word_le(fcn, 1)
    s = arch.get_bit_in_word_le(fcn, 0)
    result = 0
    b = 0
    i = 0
    while i < 16 and i < idx1:
        b = arch.get_bit_in_word_le(x, i)
        result = arch.put_bit_in_word_le(16, result, i, b)
        i += 1
    while i < 16 and i <= idx2:
        b = lut(p, q, r, s, arch.get_bit_in_word_le(x, i), arch.get_bit_in_word_le(y, i))
        result = arch.put_bit_in_word_le(16, result, i, b)
        i += 1
    while i < 16:
        b = arch.get_bit_in_word_le(x, i)
        result = arch.put_bit_in_word_le(16, result, i, b)
        i += 1
    return result

def apply_logic_fcn_word(fcn, x, y):
    common.mode.devlog(f"apply_logic_fcn_word fcn={fcn} x={word_to_hex4(x)} y={word_to_hex4(y)}")
    p = arch.get_bit_in_word_le(fcn, 3)
    q = arch.get_bit_in_word_le(fcn, 2)
    r = arch.get_bit_in_word_le(fcn, 1)
    s = arch.get_bit_in_word_le(fcn, 0)
    result = 0
    for i in range(16):
        z = lut(p, q, r, s, arch.get_bit_in_word_le(x, i), arch.get_bit_in_word_le(y, i))
        if z == 1:
            result = result | arch.mask_to_set_bit_le(i)
    common.mode.devlog(f"apply_logic_fcn_word result={word_to_hex4(result)}")
    return result

# ------------------------------------------------------------------------
# Words, binary numbers, and two's complement integers
# ------------------------------------------------------------------------

const8000 = 32768  # 2^15
constffff = 65535  # 2^16 - 1
const10000 = 65536  # 2^16

min_bin = 0
max_bin = 65535
min_tc = -32768
max_tc = 32767

word_true = 1
word_false = 0

def bool_to_word(x):
    return word_true if x else word_false

def word_to_bool(x):
    return not (x == 0)

# ------------------------------------------------------------------------
# Indexing a bit in a word
# ------------------------------------------------------------------------

def extract_bit(w, i):
    select = 1 << i
    x = w & select
    result = 0 if x == 0 else 1
    common.mode.devlog(f"extract_bit w={word_to_hex4(w)} i={i} result={result}")
    return result

def set_bit(w, i, b):
    select = limit16(1 << i)
    if b == 0:
        mask = word_invert(select)
        result = w & mask
    else:
        mask = select
        result = w | mask
    common.mode.devlog(f"set_bit w={word_to_hex4(w)} i={i} b={b} result={word_to_hex4(result)}")
    return result

# ------------------------------------------------------------------------
# Converting between binary words and two's complement integers
# ------------------------------------------------------------------------

def word_to_int(w):
    x = assert16(w)
    return x if x < const8000 else x - const10000

def int_to_word(x):
    # Python integers handle arbitrary size, so we need to simulate 16-bit overflow
    # For negative numbers, add 2^16 to get the two's complement representation
    result = x % const10000
    if result < 0:
        result += const10000
    common.mode.devlog(f"int_to_word {x} returning {result}")
    return result

def show_word(w):
    if min_bin <= w <= max_bin:
        return f"{word_to_hex4(w)} bin={w} tc={word_to_int(w)}"
    else:
        return f"word {w} is invalid: out of range"

# ------------------------------------------------------------------------
# Operating on fields of a word
# ------------------------------------------------------------------------

def split_word(x):
    y = assert16(x)
    s = y & 0x000F
    y = y >> 4
    r = y & 0x000F
    y = y >> 4
    q = y & 0x000F
    y = y >> 4
    p = y & 0x000F
    return [p, q, r, s]

# ------------------------------------------------------------------------
# Hexadecimal notation
# ------------------------------------------------------------------------

hex_digit = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f']

def word_to_hex4(x):
    p, q, r, s = split_word(limit16(x))
    result = hex_digit[p] + hex_digit[q] + hex_digit[r] + hex_digit[s]
    return result

def word_to_hex8(x):
    y = limit32(x)
    h = y & 0x000F
    y = y >> 4
    g = y & 0x000F
    y = y >> 4
    f = y & 0x000F
    y = y >> 4
    e = y & 0x000F
    y = y >> 4
    d = y & 0x000F
    y = y >> 4
    c = y & 0x000F
    y = y >> 4
    b = y & 0x000F
    y = y >> 4
    a = y & 0x000F
    return hex_digit[a] + hex_digit[b] + hex_digit[c] + hex_digit[d] + \
           ' ' + hex_digit[e] + hex_digit[f] + hex_digit[g] + hex_digit[h]

def hex4_to_word(h):
    if len(h) != 4:
        return float('nan')
    return (16**3 * hex_char_to_int(h[0]) +
            16**2 * hex_char_to_int(h[1]) +
            16**1 * hex_char_to_int(h[2]) +
            hex_char_to_int(h[3]))

def hex_char_to_int(cx):
    c = ord(cx)
    if ord('0') <= c <= ord('9'):
        return c - ord('0')
    elif ord('a') <= c <= ord('f'):
        return 10 + c - ord('a')
    elif ord('A') <= c <= ord('F'):
        return 10 + c - ord('A')
    else:
        return float('nan')

# ------------------------------------------------------------------------
# Bitwise logic on words
# ------------------------------------------------------------------------

def word_invert(x):
    return x ^ 0x0000FFFF

# ------------------------------------------------------------------------
# Basic addition and subtraction
# ------------------------------------------------------------------------

def bin_add(x, y):
    r = x + y
    return r & 0x0000FFFF

def incr_address(es, x, i):
    r = (x + i) & es.address_mask
    return r

# ------------------------------------------------------------------------
# Operations for the instructions
# ------------------------------------------------------------------------

def op_shift(a, k):
    i = word_to_int(k)
    primary = shift_l(a, i) if i > 0 else shift_r(a, -i)
    secondary = 0
    return [primary, secondary]

def shift_l(x, k):
    return truncate_word(x << k)

def shift_r(x, k):
    return truncate_word(x >> k) # Use >> for arithmetic right shift

def addition_cc(c, a, b, primary, sum_val):
    msba = arch.get_bit_in_word_le(a, 15)
    msbb = arch.get_bit_in_word_le(b, 15)
    msbsum = arch.get_bit_in_word_le(sum_val, 15)
    carry_out = arch.get_bit_in_word_le(sum_val, 16) if sum_val >= 2**16 else 0 # Check for 17th bit
    bin_overflow = carry_out == 1
    tc_overflow = (msba == 0 and msbb == 0 and msbsum == 1) or \
                  (msba == 1 and msbb == 1 and msbsum == 0)
    is0 = primary == 0
    bin_pos = sum_val != 0
    tc_pos = not tc_overflow and msbsum == 0
    tc_neg = not tc_overflow and msbsum == 1

    secondary = 0
    if bin_overflow: secondary |= arch.ccV
    if bin_overflow: secondary |= arch.ccC
    if tc_overflow: secondary |= arch.ccv
    if is0: secondary |= arch.ccE
    if bin_pos: secondary |= arch.ccG
    if tc_neg: secondary |= arch.ccl
    if tc_pos: secondary |= arch.ccg

    return secondary

def op_nop(a, b):
    pass

def op_add(c, a, b):
    sum_val = a + b
    primary = sum_val & 0x0000FFFF
    secondary = addition_cc(c, a, b, primary, sum_val)
    return [primary, secondary]

def op_addc(c, a, b):
    sum_val = a + b + arch.get_bit_in_word_le(c, arch.bit_ccC)
    primary = sum_val & 0x0000FFFF
    secondary = addition_cc(c, a, b, primary, sum_val)
    return [primary, secondary]

def op_sub(c, a, b):
    sum_val = a + word_invert(b) + 1
    primary = sum_val & 0x0000FFFF
    secondary = addition_cc(c, a, b, primary, sum_val)
    return [primary, secondary]

def op_mul(c, a, b):
    aint = word_to_int(a)
    bint = word_to_int(b)
    p = aint * bint
    primary = p & 0x0000FFFF
    tc_overflow = not (min_tc <= p <= max_tc)
    secondary = arch.ccv if tc_overflow else 0
    return [primary, secondary]

def op_muln(c, a, b):
    k16 = 2**16
    product = a * b
    primary = product % k16
    secondary = product // k16
    common.mode.devlog(f"op_muln c={c} a={a} b={b} prim={primary} sec={secondary}")
    return [primary, secondary]

def op_divn(c, a, b):
    k16 = 2**16
    dividend = k16 * c + a
    if b == 0:
        # Handle division by zero, set appropriate flags/errors
        # For now, return default values or raise an error
        return [0, 0, 0] # Or raise an exception

    quotient = dividend // b
    remainder = dividend % b
    qhigh = quotient // k16
    qlow = quotient % k16
    primary = qlow
    secondary = qhigh
    tertiary = remainder
    common.mode.devlog(f"op_divn c={c} a={a} b={b} prim={primary} sec={secondary} ter={tertiary}")
    return [primary, secondary, tertiary]

def op_div(c, a, b):
    aint = word_to_int(a)
    bint = word_to_int(b)
    if bint == 0:
        # Handle division by zero, set appropriate flags/errors
        # For now, return default values or raise an error
        return [0, 0] # Or raise an exception

    primary = int_to_word(aint // bint)  # Knuth quotient
    secondary = int_to_word(aint % bint) # Knuth mod
    return [primary, secondary]

def op_cmp(c, a, b):
    aint = word_to_int(a)
    bint = word_to_int(b)
    lt_tc = aint < bint
    lt_bin = a < b
    eq = a == b
    gt_tc = aint > bint
    gt_bin = a > b

    cc = c
    cc = arch.put_bit_in_word_le(16, cc, arch.bit_ccE, eq)
    cc = arch.put_bit_in_word_le(16, cc, arch.bit_ccG, gt_bin)
    cc = arch.put_bit_in_word_le(16, cc, arch.bit_ccg, gt_tc)
    cc = arch.put_bit_in_word_le(16, cc, arch.bit_ccl, lt_tc)
    cc = arch.put_bit_in_word_le(16, cc, arch.bit_ccL, lt_bin)

    common.mode.devlog(f"op_cmp a={a} b={b} aint={aint} bint={bint}")
    common.mode.devlog(f"op_cmp lt_bin={lt_bin} gt_bin={gt_bin}")
    common.mode.devlog(f"op_cmp lt_tc={lt_tc} gt_tc={gt_tc}")
    common.mode.devlog(f"op_cmp eq={eq}")
    common.mode.devlog(f"op_cmp cc={cc} {arch.show_cc(cc)}")
    return cc

def op_cmplt(a, b):
    aint = word_to_int(a)
    bint = word_to_int(b)
    primary = bool_to_word(aint < bint)
    return primary

def op_cmpeq(a, b):
    primary = bool_to_word(a == b)
    return primary

def op_cmpgt(a, b):
    aint = word_to_int(a)
    bint = word_to_int(b)
    primary = bool_to_word(aint > bint)
    return primary

def op_inv(a):
    primary = word_invert(a)
    return primary

def op_and(a, b):
    primary = a & b
    return primary

def op_or(a, b):
    primary = a | b
    return primary

def op_xor(a, b):
    primary = a ^ b
    return primary

def calculate_extract(wsize, wmask, dest, src,
                      dest_right,
                      src_right, src_left):
    field_size = src_left - src_right + 1
    dest_left = dest_right + field_size - 1
    dmask = field_mask(wsize, wmask, dest_left, field_size)
    dmaski = (~dmask) & wmask
    dclear = dest & dmaski

    smask = field_mask(wsize, wmask, src_left, field_size)
    sclear = src & smask

    p = sclear >> (src_left - field_size + 1)
    q = p << (dest_left - field_size + 1)
    r = dclear | q
    common.mode.devlog(f"calculate_extract wsize={wsize} wmask={word_to_hex4(wmask)}" +
                       f" dest={word_to_hex4(dest)}" +
                       f" src={word_to_hex4(src)}" +
                       f" dest_right={dest_right}" +
                       f" dest_left={dest_left}" +
                       f" src_right={src_right}" +
                       f" src_left={src_left}" +
                       f" field_size={field_size}" +
                       f" dmask={word_to_hex4(dmask)}" +
                       f" dmaski={word_to_hex4(dmaski)}" +
                       f" dclear={word_to_hex4(dclear)}" +
                       f" smask={word_to_hex4(smask)}" +
                       f" sclear={word_to_hex4(sclear)}" +
                       f" p={word_to_hex4(p)}" +
                       f" q={word_to_hex4(q)}" +
                       f" r={word_to_hex4(r)}")
    return r

def field_mask(wsize, wmask, i, fsize):
    p = wmask >> (wsize - fsize)
    q = p << (i - fsize + 1)
    common.mode.devlog(f"field_mask wsize={wsize} wmask={word_to_hex4(wmask)}" +
                       f" i={i} fsize={fsize} p={word_to_hex4(p)} q={word_to_hex4(q)}")
    return q

def calculate_extracti(wsize, fsize, x, xi, y, yi):
    xx = (~x) & 0xFF
    p = (((xx << xi) & 0xFFFF) >> (wsize - fsize)) << (wsize - yi - fsize)
    dmask = (0xFFFF >> (wsize - fsize)) << (wsize - yi - fsize)
    dmaski = (~dmask) & 0xFFFF
    z = (y & dmaski) | p
    common.mode.devlog(f"calculate_extract wsize={wsize} fsize={fsize}" +
                       f" xi={xi} yi={yi}" +
                       f" x={word_to_hex4(x)}" +
                       f" dmask={word_to_hex4(dmask)}" +
                       f" p={word_to_hex4(p)}" +
                       f" z={word_to_hex4(z)}")
    return z

# Test functions (for internal use or separate test suite)

def test_op(g, opn, op, c, a, b, expect):
    common.mode.devlog(f"test_op {opn} {c} {a} {b}")
    common.mode.devlog(f"  c = {show_word(c)} [{arch.show_cc(c)}]")
    common.mode.devlog(f"  a = {show_word(a)}")
    common.mode.devlog(f"  b = {show_word(b)}")
    primary, secondary = g(op, c, a, b)
    common.mode.devlog(f"  primary = {show_word(primary)}")
    common.mode.devlog(f"  secondary = {show_word(secondary)} [{arch.show_cc(secondary)}]")
    common.mode.devlog(f"  expecting {expect}")

def g_r(op, c, a, b):
    return op(a)

def g_rr(op, c, a, b):
    return op(a, b)

def g_crr(op, c, a, b):
    return op(c, a, b)

def test_r(opn, op, a, expect):
    return test_op(g_r, opn, op, 0, a, 0, expect)

def test_rr(opn, op, a, b, expect):
    return test_op(g_rr, opn, op, 0, a, b, expect)

def test_crr(opn, op, c, a, b, expect):
    return test_op(g_crr, opn, op, c, a, b, expect)

def test_mul():
    test_rr("mul", op_mul, 2, 3, "6 []")
    test_rr("mul", op_mul, 5, int_to_word(-7), "-35 []")
    test_rr("mul", op_mul, int_to_word(-3), int_to_word(-10), "30 []")

def test_div():
    test_rr("div", op_div, 35, 7, "5 0")
    test_rr("div", op_div, int_to_word(-9), 3, "-3 0")
    test_rr("div", op_div, 49, int_to_word(-8), "6 1")

def test_calculate_export():
    common.mode.devlog("test_calculate_export")
    calculate_extract(16, 0xFFFF, 8, 0, 0, 0, 0) # Example values, adjust as needed
    calculate_extract(16, 0xFFFF, 8, 0, 4, 0, 0)
    calculate_extract(16, 0xFFFF, 8, 0, 8, 0, 0)
    calculate_extract(16, 0xFFFF, 8, 0, 10, 0, 0)
    calculate_extract(16, 0xFFFF, 8, 0, 12, 0, 0)
    calculate_extract(16, 0xFFFF, 3, 7, 9, 0, 0) # 007c = 0000 0000 0111 11000
