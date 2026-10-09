from riscvmodel.code import decode, MachineDecodeError
from riscvmodel.isa import Instruction

from bitstring import BitArray
import os
import argparse
import copy
import importlib
import os
from abc import ABC


MemSize = 1000 # memory size, in reality, the memory size should be 2^32, but for this lab, for the space resaon, we keep it as this large number, but the memory is still 32-bit addressable.

class InsMem(object):
    def __init__(self, name, ioDir, **kwargs):
        self.id = name
        if "ioTest" not in kwargs:
            input_file_path = ioDir
        else:
            input_file_path = kwargs["ioTest"] + f"/TC{kwargs['tc']}"
        print(input_file_path)

        with open(input_file_path + "/imem.txt") as im:
            self.IMem = [data.replace("\n", "") for data in im.readlines()]

    def readInstr(self, ReadAddress):
        #read instruction memory
        #return 32 bit hex val
        ReadAddress = ReadAddress - ReadAddress % 4
        if len(self.IMem) < ReadAddress + 4:
            raise Exception("Instruction MEM - Out of bound access")
        return "".join(self.IMem[ReadAddress: ReadAddress + 4])
          
class DataMem(object):
    def __init__(self, name, ioDir, **kwargs):
        self.id = name
        self.ioDir = ioDir

        if "ioTest" not in kwargs:
            input_file_path = ioDir
        else:
            input_file_path = kwargs["ioTest"] + f"/TC{kwargs['tc']}"

        with open(input_file_path + "/dmem.txt") as dm:
            self.DMem = [data.replace("\n", "") for data in dm.readlines()]
            self.DMem += ["0" * 8] * (1000 - len(self.DMem))

    def readInstr(self, ReadAddress):
        #read data memory
        #return 32 bit hex val
         # DONE: Handle word addressing - use nearest lower multiple for 4 for address = x - x % 4
        ReadAddress = ReadAddress - ReadAddress % 4
        if len(self.DMem) < ReadAddress + 4:
            raise Exception("Data MEM - Out of bound access")
        return BitArray(bin="".join(self.DMem[ReadAddress: ReadAddress + 4])).int32
        
    def writeDataMem(self, address, WriteData):
        # write data into byte addressable memory
        # DONE: Handle word addressing - use nearest lower multiple for 4 for address = x - x % 4
        address = address - address % 4
        WriteData = '{:032b}'.format(WriteData & 0xffffffff)

        left, right, zeroes = [], [], []

        if address <= len(self.DMem):
            left = self.DMem[:address]
        else:
            left = self.DMem
            zeroes = ["0" * 8] * (address - len(self.DMem))
        if address + 4 <= len(self.DMem):
            right = self.DMem[address + 4:]

        self.DMem = left + zeroes + [WriteData[i: i + 8] for i in range(0, 32, 8)] + right
                     
    def outputDataMem(self):
        if self.id == 'SS':
            res_path = self.ioDir + "/" + self.id + "_DMEMResult.txt"
        else:
            res_path = self.ioDir + "/" + self.id + "_DMEMResult.txt"
        with open(res_path, "w") as rp:
            rp.writelines([str(data) + "\n" for data in self.DMem])

class IntermediateState:

    def __init__(self):
        pass

    def set_attributes(self, **kwargs):
        self.__dict__.update(kwargs)
class EXState(IntermediateState):

    def __init__(self):
        self.nop: bool = False  # NOP operation
        self.instruction_ob = None  # Decoded InstructionBase object
        self.operand1: int = 0  # operand 1 for execute
        self.operand2: int = 0  # operand 2 for execute - can be rs2 or imm or forwarded data
        self.store_data: int = 0  # sw data - result of alu
        self.destination_register: int = 0  # destination register - rd
        # self.alu_operation: str = None  # not required for now
        self.read_data_mem: bool = False  # Flag - identify if we need to read from mem (MEM Stage)
        self.write_data_mem: bool = False  # Flag - identify if we need to write to mem (MEM Stage)
        self.write_back_enable: bool = False  # Flag - identify if result needs to be written back to register
        self.halt: bool = False  # Flag - identify end of program
        super(EXState, self).__init__()

    def __str__(self):
        return "\n".join([f"EX.{key}: {val}" for key, val in self.__dict__.items()])


class MEMState(IntermediateState):

    def __init__(self):
        self.nop: bool = False  # NOP operation
        self.instruction_ob = None  # Decoded InstructionBase object
        self.data_address: int = 0  # address for read / write DMEM operation
        self.store_data: int = 0  # data to be written to MEM for SW instruction or passed to WB
        self.write_register_addr: int = 0  # register to load data from MEM
        self.read_data_mem: bool = False  # Flag - identify if we need to read from mem (MEM Stage)
        self.write_data_mem: bool = False  # Flag - identify if we need to write to mem (MEM Stage)
        self.write_back_enable: bool = False  # Flag - identify if result needs to be written back to register
        self.halt: bool = False  # Flag - identify end of program
        super(MEMState, self).__init__()

    def __str__(self):
        return "\n".join([f"MEM.{key}: {val}" for key, val in self.__dict__.items()])


class WBState(IntermediateState):

    def __init__(self):
        self.nop = False  # NOP operation
        self.instruction_ob = None  # Decoded InstructionBase object
        self.store_data: int = 0  # data to be written to MEM for SW instruction
        self.write_register_addr: int = 0  # register to load data from MEM
        self.write_back_enable: bool = False  # Flag - identify if result needs to be written back to register
        self.halt: bool = False  # Flag - identify end of program
        super(WBState, self).__init__()

    def __str__(self):
        return "\n".join([f"WB.{key}: {val}" for key, val in self.__dict__.items()])


class IntermediateState:

    def __init__(self):
        pass

    def set_attributes(self, **kwargs):
        self.__dict__.update(kwargs)

class RegisterFile(object):
    def __init__(self, ioDir):
        self.outputFile = ioDir + "RFResult.txt"
        self.Registers = [0x0 for i in range(32)]
    
    def readRF(self, Reg_addr):
        # Fill in
        return self.Registers[Reg_addr]
    
    def writeRF(self, Reg_addr, Wrt_reg_data):
        # Fill in
        if Reg_addr != 0:
            self.Registers[Reg_addr] = Wrt_reg_data
         
    def outputRF(self, cycle):
        op = ["-"*70+"\n", "State of RF after executing cycle:" + str(cycle) + "\n"]
        # op.extend([str(val)+"\n" for val in self.Registers])
        op.extend([f"{val:032b}\n" for val in self.Registers])
        if(cycle == 0): perm = "w"
        else: perm = "a"
        with open(self.outputFile, perm) as file:
            file.writelines(op)

class State(object):
    def __init__(self):
        self.IF = {"nop": False, "PC": 0, "instruction_count":0, "halt":False}
        self.ID = {"nop": False, "instruction_byte":"", "halt":False}
        self.EX = {"nop": False,"instruction_ob": None, "Read_data1": 0, "Read_data2": 0, "Imm": 0, "Rs": 0, "Rt": 0, "Wrt_reg_addr": 0, "is_I_type": False, "rd_mem": 0, 
                   "wrt_mem": 0, "alu_op": 0, "wrt_enable": 0,"halt":False}
        self.MEM = {"nop": False, "instruction_ob": None,"data_address":0,"ALUresult": 0, "Store_data": 0, "Rs": 0, "Rt": 0, "Wrt_reg_addr": 0, "rd_mem": 0, 
                   "wrt_mem": 0, "wrt_enable": 0,"halt":False}
        self.WB = {"nop": False,"instruction_ob": None, "store_data": 0, "Rs": 0, "Rt": 0, "Wrt_reg_addr": 0, "wrt_enable": 0,"halt":False}
        
class Core(object):
    def __init__(self, ioDir, imem, dmem):
        self.myRF = RegisterFile(ioDir)
        self.cycle = 0
        self.halted = False
        self.ioDir = ioDir
        self.state = State()
        self.nextState = State()
        self.ext_imem = imem
        self.ext_dmem = dmem
    def calculate_performance_metrics(self):
        cpi = float(self.cycle) / self.state.IF["instruction_count"]
        ipc = 1 / cpi

        result_format = f"-----------------------------{self.stages} Core Performance Metrics-----------------------------\n" \
                        f"Number of cycles taken: {self.cycle}\n" \
                        f"Total number of instructions: {self.state.IF['instruction_count']}\n" \
                        f"Cycles per instruction: {cpi}\n" \
                        f"Instructions per cycle: {ipc}\n"

        write_mode = "w" if self.stages == "Single Stage" else "a"

        with open(self.ioDir[:-3] + "PerformanceMetrics_Result.txt", write_mode) as file:
            file.write(result_format)
def get_instruction_class(mnemonic: str):
        try:
            if mnemonic == "lb":
                mnemonic = "lw"
            cls = getattr(importlib.import_module('instructions'), mnemonic.upper())
            return cls
        except AttributeError as e:
            raise Exception("Invalid Instruction")

class SingleStageCore(Core):
    def __init__(self, ioDir: str, imem: InsMem, dmem: DataMem):
        super(SingleStageCore, self).__init__(ioDir + "/SS_", imem, dmem)
        self.opFilePath = ioDir + "/StateResult_SS.txt"
        self.stages = "Single Stage"
        
    

    def step(self):
        # IF
        instruction_bytes = self.ext_imem.readInstr(self.state.IF["PC"])
        if instruction_bytes == "1" * 32:
            self.nextState.IF["nop"] = True
        else:
            self.nextState.IF["PC"] += 4
            self.nextState.IF["instruction_count"]= self.nextState.IF["instruction_count"]+ 1

        try:
            # ID
            instruction: Instruction = decode(int(instruction_bytes, 2))
            instruction_ob: InstructionBaseClass = get_instruction_class(instruction.mnemonic)(instruction,
                                                                                            self.ext_dmem, self.myRF,
                                                                                            self.state,
                                                                                            self.nextState)
            # Ex
            alu_result = instruction_ob.execute()
            # Load/Store (MEM)
            mem_result = instruction_ob.mem(alu_result=alu_result)
            # WB
            wb_result = instruction_ob.wb(mem_result=mem_result, alu_result=alu_result)
        except MachineDecodeError as e:
            if "{:08x}".format(e.word) == 'ffffffff':
                pass
            else:
                raise Exception("Invalid Instruction to Decode")
        # self.halted = True
        if self.state.IF["nop"]:
            self.nextState.IF["instruction_count"] = self.nextState.IF["instruction_count"] + 1
            self.halted = True

        self.myRF.outputRF(self.cycle)  # dump RF
        self.printState(self.nextState, self.cycle)  # print states after executing cycle 0, cycle 1, cycle 2 ...

        # The end of the cycle and updates the current state with the values calculated in this cycle
        self.state = copy.deepcopy(self.nextState)
        # self.nextState = copy.deepcopy(self.nextState)
        self.cycle += 1

    def printState(self, state, cycle):
        printstate = ["-" * 70 + "\n", "State after executing cycle: " + str(cycle) + "\n"]
        printstate.append("IF.PC: " + str(state.IF["PC"]) + "\n")
        printstate.append("IF.nop: " + str(state.IF["nop"]) + "\n")

        if (cycle == 0):
            perm = "w"
        else:
            perm = "a"
        with open(self.opFilePath, perm) as wf:
            wf.writelines(printstate)

class FiveStageCore(Core):
    def __init__(self, ioDir, imem, dmem):
        super(FiveStageCore, self).__init__(ioDir + "\\FS_", imem, dmem)
        self.opFilePath = ioDir + "\\StateResult_FS.txt"

    def step(self):
        # Your implementation
        # --------------------- WB stage ---------------------
        
        
        
        # --------------------- MEM stage --------------------
        
        
        
        # --------------------- EX stage ---------------------
        
        
        
        # --------------------- ID stage ---------------------
        
        
        
        # --------------------- IF stage ---------------------
        
        self.halted = True
        if self.state.IF["nop"] and self.state.ID["nop"] and self.state.EX["nop"] and self.state.MEM["nop"] and self.state.WB["nop"]:
            self.halted = True
        
        self.myRF.outputRF(self.cycle) # dump RF
        self.printState(self.nextState, self.cycle) # print states after executing cycle 0, cycle 1, cycle 2 ... 
        
        self.state = self.nextState #The end of the cycle and updates the current state with the values calculated in this cycle
        self.cycle += 1

    def printState(self, state, cycle):
        printstate = ["-"*70+"\n", "State after executing cycle: " + str(cycle) + "\n"]
        printstate.extend(["IF." + key + ": " + str(val) + "\n" for key, val in state.IF.items()])
        printstate.extend(["ID." + key + ": " + str(val) + "\n" for key, val in state.ID.items()])
        printstate.extend(["EX." + key + ": " + str(val) + "\n" for key, val in state.EX.items()])
        printstate.extend(["MEM." + key + ": " + str(val) + "\n" for key, val in state.MEM.items()])
        printstate.extend(["WB." + key + ": " + str(val) + "\n" for key, val in state.WB.items()])

        if(cycle == 0): perm = "w"
        else: perm = "a"
        with open(self.opFilePath, perm) as wf:
            wf.writelines(printstate)


if __name__ == "__main__":
    # parse arguments for input file location
    parser = argparse.ArgumentParser(description='RV32I processor')
    parser.add_argument('--iodir', default="", type=str, help='Directory containing the input files.')
    parser.add_argument("--testpath", default="", type=str, help="Test Case Path")
    args = parser.parse_args()
    test_case_number = 1

    ioDir = os.path.abspath(args.iodir)
    ioTest = os.path.abspath(args.testpath)

    print("IO Directory:", ioDir)
    print("Test Path:", ioTest)

    if ioTest == "":
        imem = InsMem("Imem", ioDir, ioTest=ioTest, tc=test_case_number)
        dmem_ss = DataMem("SS", ioDir, ioTest=ioTest, tc=test_case_number)    
    else:
        imem = InsMem("Imem", ioDir)
        dmem_ss = DataMem("SS", ioDir)
    

    ssCore = SingleStageCore(ioDir, imem, dmem_ss)


    while True:
        if not ssCore.halted:
            ssCore.step()
        else:
            break

    # dump SS and FS data mem.
    dmem_ss.outputDataMem()
    

    # dumps SS and DS Performance
    ssCore.calculate_performance_metrics()
