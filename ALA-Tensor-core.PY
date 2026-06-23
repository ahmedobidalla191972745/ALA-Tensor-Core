# =====================================================================
# منظومة مترجم معمارية ALA التنسورية - الإصدار الصافي بمجمع ومولد الباينري
# الواجهة الأمامية: توليد إحداثيات صمّاء متفرقة (Pure Sparse COO)
# وحدة المجمِّع: ضغط وتشفير الإحداثيات إلى ملف باينري حقيقي (.bin) عبر مكتبة struct
# الواجهة الخلفية: شاحن الباينري الافتراضي وتفكيك الإحداثيات بالمعالج O(1)
# المهندس: أحمد حامد أحمد عبيد الله
# =====================================================================

import json
import re
import struct

# =====================================================================
# أولاً: الواجهة الأمامية للمترجم الأولي (Frontend Compiler)
# =====================================================================
class ALATensorFrontend:
    def __init__(self):
        self.d_R = 250   # سقف فضاء الجذور المعجمية
        self.d_W = 15    # أبعاد قوالب الأوزان
        self.d_D = 4     # أبعاد الحركات النحوية الموضعية

        self.root_to_index = {
            "خ ر ج": 0, "ن ق ل": 1, "ج م ع": 2, "ن ق ص": 3,
            "ع د ل": 4, "ك ب ر": 5, "ص غ ر": 6, "ذ ه ب": 7,
            "ح ي ن": 8, "ب ا ب": 9, "ن ت ج": 10, "ط ل ق": 11
        }

        self.weight_templates = {
            "افعل":  {"id": 0, "gating_delta": 3, "pattern": r"^ا([أ-ي])([أ-ي])([أ-ي])$"}, 
            "فعل":   {"id": 1, "gating_delta": 0, "pattern": r"^([أ-ي])([أ-ي])([أ-ي])$"},    
            "فعيلة": {"id": 2, "gating_delta": 0, "pattern": r"^([أ-ي])([أ-ي])ي([أ-ي])ة$"},  
            "مفعل":  {"id": 3, "gating_delta": 0, "pattern": r"^م([أ-ي])([أ-ي])([أ-ي])$"},   
            "فاعل":  {"id": 4, "gating_delta": 0, "pattern": r"^([أ-ي])ا([أ-ي])([أ-ي])$"}    
        }

        self.sentence_signatures = {
            (3,):            "HALT_OP",     
            (3, 0, 0):       "THREE_OP",    
            (3, 0, 0, 0, 0): "COND_BRANCH"  
        }

    def _subsequence_match(self, word_clean):
        for weight_name, weight_data in self.weight_templates.items():
            match = re.match(weight_data["pattern"], word_clean)
            if match:
                root_chars = match.groups()     
                root_str = " ".join(root_chars) 
                if root_str in self.root_to_index:
                    return {
                        "root_idx": self.root_to_index[root_str],
                        "weight_id": weight_data["id"],
                        "delta": weight_data["gating_delta"]
                    }
        raise NameError(f"خطأ صرفي عتادي: الكلمة '{word_clean}' لا تنتمي لمعجم المعمارية الحالية.")

    def _tokenize_and_clean(self, instruction_str):
        stripped = instruction_str.strip()
        if not stripped.endswith("."):
            raise SyntaxError("خطأ بنيوي قاتل: غياب بواب النهاية الحتمي للمصفوفة '.'")
        return stripped[:-1].strip().split()

    def generate_sparse_workspace(self, instruction_str):
        tokens = self._tokenize_and_clean(instruction_str)
        words_ir = [self._subsequence_match(t) for t in tokens]
        sentence_signature = tuple(w_ir["delta"] for w_ir in words_ir)
        
        if sentence_signature not in self.sentence_signatures:
            raise SyntaxError(f"خطأ تركيبي: التوقيع الحركي {list(sentence_signature)} غير معرف عتادياً.")
            
        operation_type = self.sentence_signatures[sentence_signature]
        sparse_workspace = {
            "operation_type": operation_type,
            "tensor_rank_n": len(words_ir),
            "active_coordinates": [] 
        }

        for w_ir in words_ir:
            flat_coordinate = (w_ir["root_idx"] * self.d_W * self.d_D) + (w_ir["weight_id"] * self.d_D) + w_ir["delta"]
            sparse_workspace["active_coordinates"].append(flat_coordinate)

        return sparse_workspace


# =====================================================================
# ثانياً: وحدة مجمّع وشاحن الباينري للـ MVP (ALA MVP Assembler & Loader)
# =====================================================================
class ALAMVPAssembler:
    def __init__(self):
        # خريطة البايتات الحتمية لتشفير بوابات العمليات (Opcodes Map)
        self.op_to_bytecode = {
            "HALT_OP": 0x00,
            "THREE_OP": 0x01,
            "COND_BRANCH": 0x02
        }
        self.bytecode_to_op = {v: k for k, v in self.op_to_bytecode.items()}

    def assemble_to_binary(self, compiled_bundle, output_filepath="program.bin"):
        """تحويل مخرجات الـ Frontend المشفرة وتعبئتها في ملف ثنائي مصمت على القرص"""
        binary_data = bytearray()

        for line in compiled_bundle:
            opcode = self.op_to_bytecode[line["operation_type"]]
            rank_n = line["tensor_rank_n"]
            coordinates = line["active_coordinates"]

            # 1. حزم الرأسية (Header): 1 بايت للعملية + 1 بايت للطول (Rank N)
            binary_data.extend(struct.pack("BB", opcode, rank_n))
            # 2. حزم البيانات: كل إحداثي يتم ضغطه في 2 بايت (16-bit Unsigned Short 'H')
            binary_data.extend(struct.pack(f"{rank_n}H", *coordinates))

        with open(output_filepath, "wb") as f:
            f.write(binary_data)
        
        print(f"[ASSEMBLER] تم توليد باينري الآلة بنجاح: '{output_filepath}' | الحجم الصافي: {len(binary_data)} بايت.")

    def disassemble_and_load(self, input_filepath="program.bin"):
        """محاكاة شاحن العتاد: قراء بايتات الملف الثنائي من القرص وإعادة بنائها للتنفيذ المعزول"""
        compiled_bundle = []

        with open(input_filepath, "rb") as f:
            while True:
                # قراءة بايتات الرأسية للسطر (2 بايت حصرًا)
                header_bytes = f.read(2)
                if not header_bytes:
                    break # الوصول لنهاية الملف الصافي EOF

                opcode, rank_n = struct.unpack("BB", header_bytes)
                
                # قراءة الإحداثيات التابعة للسطر بناءً على الطول المسجل بالرأسية (كل إحداثي 2 بايت)
                coords_bytes = f.read(rank_n * 2)
                coordinates = list(struct.unpack(f"{rank_n}H", coords_bytes))

                # إعادة التشكيل البنيوي الصامت لإدخاله في الـ Backend
                compiled_bundle.append({
                    "operation_type": self.bytecode_to_op[opcode],
                    "tensor_rank_n": rank_n,
                    "active_coordinates": coordinates
                })

        print(f"[LOADER] تم تحميل وفك ضغط الباينري عتادياً من القرض الصلب وجاهز للإطلاق.")
        return compiled_bundle


# =====================================================================
# ثالثاً: المترجم الخلفي الافتراضي المعزول نقيّاً (Backend Compiler)
# =====================================================================
class ALATensorBackend:
    def __init__(self):
        self.d_W = 15
        self.d_D = 4
        self.d_R = 250
        self.RAM = [0] * self.d_R
        self.Z_FLAG = 0     
        self.PC = 0         
        self.halted = False 

    def load_initial_data(self, address, value):
        if address >= self.d_R:
            raise IndexError("العنوان خارج الحدود.")
        self.RAM[address] = self._apply_16bit_mask(value)

    def _apply_16bit_mask(self, val):
        return ((val + 32768) % 65536) - 32768

    def decode_coordinate(self, flat_coordinate):
        base_divisor = self.d_W * self.d_D 
        root_idx = flat_coordinate // base_divisor
        remainder = flat_coordinate % base_divisor
        weight_id = remainder // self.d_D
        delta = remainder % self.d_D
        return root_idx, weight_id, delta

    def execute_step(self, compiled_line):
        op_type = compiled_line["operation_type"]
        coords_data = compiled_line["active_coordinates"]

        if op_type == "HALT_OP":
            self.halted = True
            print(f"[ALU] السطر {self.PC}: تفعيل أمر الخروج الحتمي للمصفوفة. إيقاف المعالج.")
            return

        elif op_type == "THREE_OP":
            verb_root, _, _ = self.decode_coordinate(coords_data[0]) 
            src_reg, _, _   = self.decode_coordinate(coords_data[1]) 
            dest_reg, _, _  = self.decode_coordinate(coords_data[2]) 

            if verb_root == 1:    
                self.RAM[dest_reg] = self.RAM[src_reg]
                print(f"[ALU] السطر {self.PC}: تنفيذ أمر [نقل] -> نسخ القيمة ({self.RAM[src_reg]}) من عنوان الذاكرة [{src_reg}] إلى عنوان الذاكرة [{dest_reg}]")
                self.PC += 1

            elif verb_root == 2:  
                res = self.RAM[dest_reg] + self.RAM[src_reg]
                self.RAM[dest_reg] = self._apply_16bit_mask(res)
                print(f"[ALU] السطر {self.PC}: تنفيذ أمر [اجمع] -> الموقع الاستاتيكي [{dest_reg}] أصبح يحتوي على ناتج الجمع المحدث: ({self.RAM[dest_reg]})")
                self.PC += 1

            elif verb_root == 3:  
                res = self.RAM[dest_reg] - self.RAM[src_reg]
                self.RAM[dest_reg] = self._apply_16bit_mask(res)
                print(f"[ALU] السطر {self.PC}: تنفيذ أمر [انقص] -> الموقع [{dest_reg}] أصبح يحتوي على: ({self.RAM[dest_reg]})")
                self.PC += 1

            elif verb_root == 7:  
                target_line = self.RAM[dest_reg]
                print(f"[ALU] السطر {self.PC}: تنفيذ أمر [اذهب مطلق] -> قفز عتادي مباشر للسطر البرمجي رقم ({target_line})")
                self.PC = target_line

        elif op_type == "COND_BRANCH":
            comp_root, _, _  = self.decode_coordinate(coords_data[2]) 
            reg_target, _, _ = self.decode_coordinate(coords_data[3]) 
            reg_compare, _, _= self.decode_coordinate(coords_data[4]) 

            if comp_root == 4:  
                if self.RAM[reg_compare] == 0:
                    self.Z_FLAG = 1
                else:
                    self.Z_FLAG = 0
                
                print(f"[ALU] السطر {self.PC}: فحص الحالة الشرطية للموقع [{reg_compare}] الحالي ({self.RAM[reg_compare]}) -> حالة الـ Z_FLAG = {self.Z_FLAG}")

                if self.Z_FLAG == 1:
                    destination = self.RAM[reg_target]
                    print(f"[ALU] تحقق الشرط! قفز ديناميكي موجه إلى السطر رقم: ({destination})")
                    self.PC = destination
                else:
                    print(f"[ALU] لم يتحقق الشرط. تجاوز القفز والانتقال خطياً للسطر التالي.")
                    self.PC += 1

    def run_program_bundle(self, compiled_bundle):
        print("\n" + "="*60 + "\n[RUN] إقلاع العتاد النقي: تشغيل الشفرة الثنائية المفككة...\n" + "="*60)
        self.halted = False
        self.PC = 0
        safety_counter = 0 

        while self.PC < len(compiled_bundle) and not self.halted:
            if safety_counter > 30:
                print("\n[SAFETY KICK] تم كبح المعالج.")
                break
            current_line_data = compiled_bundle[self.PC]
            self.execute_step(current_line_data)
            safety_counter += 1

        print("\n" + "="*60 + "\n[INFO] مسح السجل الفيزيائي النهائي للمسجلات الاستاتيكية:")
        print(f"-> موقع الذاكرة الثابت 'نتيجة' (العنوان 10) = {self.RAM[10]}")
        print("="*60 + "\n")


# =====================================================================
# رابعاً: منصة تشغيل المنظومة المكتملة بخط إنتاج الباينري الكامل
# =====================================================================
if __name__ == "__main__":
    # إقلاع الكيانات الثلاثة للمنظومة
    ala_frontend = ALATensorFrontend()
    ala_assembler = ALAMVPAssembler()
    ala_backend = ALATensorBackend()

    # 1. ملف البرنامج البرمجي العربي المكتوب نصيّاً
    arabic_program_file = [
        "انقص مطلق نتيجة.",         
        "اذهب حين عادل باب نتيجة.", 
        "اذهب مطلق حين.",          
        "اخرج."                     
    ]

    # 2. التمرير عبر المترجم الأولي لتوليد مصفوفة التنسورات المتفرقة
    intermediate_bundle = []
    print("=== [FRONTEND] ضخ الأوامر اللغوية وتوليد المصفوفة المتفرقة ===")
    for line_num, code_line in enumerate(arabic_program_file):
        cleaned_line = code_line.replace("bab", "باب")
        coo_payload = ala_frontend.generate_sparse_workspace(cleaned_line)
        intermediate_bundle.append(coo_payload)
    print("[FRONTEND] تمت مرحلة الترجمة اللغوية والتسطيح التنسوري بنجاح.\n")

    # 3. تشغيل المجمِّع: أخذ البيانات من بايثون وضغطها وحفظها في ملف باينري صلب
    binary_filename = "ala_firmware.bin"
    ala_assembler.assemble_to_binary(intermediate_bundle, output_filepath=binary_filename)
    print("-" * 65)

    # 4. تشغيل الشاحن (Loader): قراءة بايتات ملف الباينري الصامت وفكها عتادياً للـ Backend
    executable_bundle = ala_assembler.disassemble_and_load(input_filepath=binary_filename)

    # 5. شحن قيم الذاكرة الاستاتيكية قبل بدء التشغيل الفعلي
    ala_backend.load_initial_data(address=11, value=1)  # مسجل 'مطلق' = 1 (مقدار الطرح الثابت)
    ala_backend.load_initial_data(address=10, value=2)  # مسجل 'نتيجة' = 2 (العداد التنازلي)
    ala_backend.load_initial_data(address=9, value=3)   # مسجل 'باب' = 3 (عنوان سطر الخروج والإنهاء)
    ala_backend.load_initial_data(address=8, value=0)   # مسجل 'حين' = 0 (عنوان سطر البداية لإعادة الدورة)

    # 6. إطلاق الشفرة الثنائية المحملة داخل قلب المعالج الافتراضي للـ Backend والتنفيذ الحقيقي
    ala_backend.run_program_bundle(executable_bundle)