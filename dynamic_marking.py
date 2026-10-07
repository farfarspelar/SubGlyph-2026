"""Marking model and explicit, controller-specific dynamic postprocessing."""
from dataclasses import dataclass, asdict, replace
from datetime import date
import re
from nc_geometry import marking_text_width

KINDS = ('Statisk text', 'Serienummer', 'Fast datum', 'Maskindatum')
DATE_FORMATS = {'YYYY-MM-DD': '%Y-%m-%d', 'YYMMDD': '%y%m%d',
                'DDMMYY': '%d%m%y', 'YYYYMMDD': '%Y%m%d'}

@dataclass
class DynamicMarking:
    kind: str = 'Statisk text'
    start: int = 1
    digits: int = 6
    leading_zeros: bool = True
    variable: str = '#520'
    position_variable: str = '#521'
    date_format: str = 'YYYY-MM-DD'
    verified_variables: tuple[str, str] | None = None

    def __setattr__(self, name, value):
        if name in ("variable", "position_variable") and getattr(self, name, value) != value:
            object.__setattr__(self, "verified_variables", None)
        object.__setattr__(self, name, value)

    def verify(self):
        self.verified_variables = (self.variable, self.position_variable)

    @property
    def verified(self):
        return self.verified_variables == (self.variable, self.position_variable)

    def to_dict(self):
        data = asdict(self)
        data.pop('verified_variables')  # Machine verification never travels with a project.
        return data

    @classmethod
    def from_dict(cls, data):
        allowed = cls().to_dict()
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def validate(self, controller):
        if self.kind not in KINDS:
            raise ValueError('Okänd märktyp.')
        if self.kind == 'Maskindatum':
            raise ValueError('Maskindatum stöds inte ännu: datumvariabler är inte verifierade.')
        if self.kind != 'Serienummer':
            return
        if controller != 'FANUC (ISO)':
            raise ValueError('Dynamiska serienummer stöds endast för FANUC Custom Macro B i testversionen.')
        if not isinstance(self.digits, int) or not 1 <= self.digits <= 8:
            raise ValueError('Antal siffror måste vara 1–8.')
        serial_digits(self.start, self.digits, self.leading_zeros)
        for variable in (self.variable, self.position_variable):
            if not re.fullmatch(r'#5[0-4][0-9]', variable):
                raise ValueError('Testversionen tillåter uttryckligen valda variabler #500–#549.')
        if self.variable == self.position_variable:
            raise ValueError('Räknare och arbetsvariabel måste vara olika.')
        if not self.verified:
            raise ValueError('Verifiera båda valda variablerna mot maskinens dokumentation.')


def serial_digits(value, digits, leading_zeros=True):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 10 ** digits:
        raise ValueError('Serienumret ryms inte i valt antal siffror.')
    text = str(value).zfill(digits) if leading_zeros else str(value)
    return [int(char) for char in text]


def format_date(value, selected_format):
    return date.fromisoformat(value).strftime(DATE_FORMATS[selected_format])


class FanucDynamicPost:
    """Inline reusable digit blocks. Writes only the two explicitly selected commons.

    Dispatch labels are owned by this post and isolated per marking row. No G91,
    coordinate-system changes, system-variable writes or implicit scratch variables.
    """
    def blocks(self, config, marking, geometry, row):
        config.validate('FANUC (ISO)')
        if marking.font_path:
            raise ValueError('Dynamiska serienummer använder SubGlyphs enlinjefont i testversionen.')
        v, pos = config.variable, config.position_variable
        base = 1000 + row * 100
        loop, advance, end, fail = [base + n for n in (1, 3, 4, 5)]
        lines = [f'(SERIENUMMER {v} ARBETSVARIABEL {pos})',
                 f'(INITIERA SEPARAT FORE FORSTA DETALJ: {v}={config.start})',
                 f'IF [{v} EQ #0] GOTO {fail}',
                 f'IF [{v} LT 0] GOTO {fail}',
                 f'IF [{v} GE {10 ** config.digits}] GOTO {fail}',
                 f'IF [{v} NE FIX[{v}]] GOTO {fail}', f'{pos}=0', f'N{loop}']
        # Each position extracts a digit, then branches to the shared geometry.
        for position in range(config.digits):
            lines.append(f'IF [{pos} EQ {position}] GOTO {base + 20 + position}')
        lines.append(f'GOTO {end}')
        for position in range(config.digits):
            divisor = 10 ** (config.digits - position - 1)
            digit = f'[FIX[{v}/{divisor}]-10*FIX[{v}/{divisor * 10}]]'
            lines.append(f'N{base + 20 + position}')
            if not config.leading_zeros and position < config.digits - 1:
                lines.append(f'IF [{v} LT {divisor}] GOTO {advance}')
            for number in range(10):
                lines.append(f'IF [{digit} EQ {number}] GOTO {base + 40 + number}')
            lines.append(f'GOTO {fail}')
        full_width = marking_text_width('0' * config.digits, marking.width, marking.character_spacing)
        for digit in range(10):
            pitch = marking.width + marking.character_spacing
            first = replace(marking, text=str(digit), horizontal_offset=-pitch * (config.digits - 1) / 2, layout_width=full_width)
            second = replace(first, horizontal_offset=first.horizontal_offset + pitch * 1000000)
            zero, one = geometry(first), geometry(second)
            lines.append(f'N{base + 40 + digit}')
            # Symbolic translation follows the same geometric transform, including C.
            for a, b in zip(zero[1:], one[1:]):
                other = {m[0]: float(m[1]) for m in re.findall(r'([XYZC])(-?[\d.]+)', b)}
                def offset(match):
                    axis, value = match.groups()
                    delta = (other.get(axis, float(value)) - float(value)) / 1000000
                    return f'{axis}[{value}+{pos}*{delta:.9f}]' if abs(delta) > 1e-8 else match[0]
                lines.append(re.sub(r'([XYZC])(-?[\d.]+)', offset, a))
            lines.append(f'GOTO {advance}')
        lines += [f'N{advance}', f'{pos}={pos}+1', f'GOTO {loop}',
                  f'N{fail}', '(OGILTIGT SERIENUMMER - AVBRYT OCH KONTROLLERA RAKNAREN)', 'M0', f'GOTO {fail}', f'N{end}', f'{v}={v}+1']
        return lines
