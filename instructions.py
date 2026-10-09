import abc
import importlib
import os
from abc import ABC

from riscvmodel.code import decode
from riscvmodel.isa import Instruction

from main import DataMem, RegisterFile, State

# Base class for all instruction types
class InstructionBaseClass(metaclass=abc.ABCMeta):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        # Initialize the common elements for instructions
        self.instruction = instruction
        self.memory = memory
        self.Registers = registers
        self.state = state
        self.nextState = nextState
        self.stages = self.memory.id  # Memory stage identifier

    # Decoding step (subclass can override)
    def decode_ss(self, *args, **kwargs):
        pass

    # Abstract method for execution stage (subclass must implement)
    @abc.abstractmethod
    def execute_ss(self, *args, **kwargs):
        pass

    # Memory access stage (subclass can override)
    def mem_ss(self, *args, **kwargs):
        pass

    # Write-back stage (subclass can override)
    def wb_ss(self, *args, **kwargs):
        pass

    # Helper methods for each pipeline stage, defaulting to their specialized counterparts
    def decode(self, *args, **kwargs):
        return self.decode_ss(*args, **kwargs)
        
    def execute(self, *args, **kwargs):
        return self.execute_ss(*args, **kwargs)

    def mem(self, *args, **kwargs):
        return self.mem_ss(*args, **kwargs)
        
    def wb(self, *args, **kwargs):
        return self.wb_ss(*args, **kwargs)

# R-type instruction (register-based)
class InstructionR(InstructionBaseClass, ABC):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        # Initialize common R-type attributes
        super(InstructionR, self).__init__(instruction, memory, registers, state, nextState)
        self.rs1 = instruction.rs1
        self.rs2 = instruction.rs2
        self.rd = instruction.rd

    # Write-back stage for R-type, writing result to destination register
    def wb_ss(self, *args, **kwargs):
        data = kwargs['alu_result']
        return self.Registers.writeRF(self.rd, data)

# I-type instruction (immediate-based)
class InstructionI(InstructionBaseClass, ABC):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        # Initialize common I-type attributes
        super(InstructionI, self).__init__(instruction, memory, registers, state, nextState)
        self.rs1 = instruction.rs1
        self.rd = instruction.rd
        self.imm = instruction.imm.value

    # Write-back stage for I-type, writing result to destination register
    def wb_ss(self, *args, **kwargs):
        data = kwargs['alu_result']
        return self.Registers.writeRF(self.rd, data)

# S-type instruction (store-based)
class InstructionS(InstructionBaseClass, ABC):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        # Initialize common S-type attributes
        super(InstructionS, self).__init__(instruction, memory, registers, state, nextState)
        self.rs1 = instruction.rs1
        self.rs2 = instruction.rs2
        self.imm = instruction.imm.value

    # Memory access stage for S-type, writing data to memory
    def mem_ss(self, *args, **kwargs):
        address = kwargs['alu_result']
        data = self.Registers.readRF(self.rs2)
        self.memory.writeDataMem(address, data)

# Implementation of specific instructions
# R-type ADD instruction
class ADD(InstructionR):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        super(ADD, self).__init__(instruction, memory, registers, state, nextState)

    # Execute stage for ADD, performs addition
    def execute_ss(self, *args, **kwargs):
        return self.Registers.readRF(self.rs1) + self.Registers.readRF(self.rs2)

# R-type SUB instruction
class SUB(InstructionR):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        super(SUB, self).__init__(instruction, memory, registers, state, nextState)

    # Execute stage for SUB, performs subtraction
    def execute_ss(self, *args, **kwargs):
        return self.Registers.readRF(self.rs1) - self.Registers.readRF(self.rs2)

# R-type OR instruction
class OR(InstructionR):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        super(OR, self).__init__(instruction, memory, registers, state, nextState)

    # Execute stage for OR, performs bitwise OR
    def execute_ss(self, *args, **kwargs):
        return self.Registers.readRF(self.rs1) | self.Registers.readRF(self.rs2)

# R-type AND instruction
class AND(InstructionR):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        super(AND, self).__init__(instruction, memory, registers, state, nextState)

    # Execute stage for AND, performs bitwise AND
    def execute_ss(self, *args, **kwargs):
        return self.Registers.readRF(self.rs1) & self.Registers.readRF(self.rs2)

# I-type LW instruction (Load Word)
class LW(InstructionI):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        super(LW, self).__init__(instruction, memory, registers, state, nextState)

    # Execute stage for LW, calculates memory address
    def execute_ss(self, *args, **kwargs):
        return self.Registers.readRF(self.rs1) + self.imm

    # Memory access stage for LW, reads from memory
    def mem_ss(self, *args, **kwargs):
        address = kwargs['alu_result']
        return self.memory.readInstr(address)

    # Write-back stage for LW, writes loaded data to destination register
    def wb_ss(self, *args, **kwargs):
        data = kwargs['mem_result']
        return self.Registers.writeRF(self.rd, data)

# S-type SW instruction (Store Word)
class SW(InstructionS):
    def __init__(self, instruction: Instruction, memory: DataMem, registers: RegisterFile, state: State,
                 nextState: State):
        super(SW, self).__init__(instruction, memory, registers, state, nextState)

    # Execute stage for SW, calculates memory address
    def execute_ss(self, *args, **kwargs):
        return self.Registers.readRF(self.rs1) + self.imm

# Dynamically fetch the instruction class based on mnemonic
def get_instruction_class(mnemonic: str):
    try:
        if mnemonic == "lb":
            mnemonic = "lw"  # Redirect "lb" to "lw" for specific handling
        cls = getattr(importlib.import_module('instructions'), mnemonic.upper())
        return cls
    except AttributeError as e:
        raise Exception("Invalid Instruction")