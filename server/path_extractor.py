import os, sys, re, math
from OCC.Core.gp import gp_Trsf, gp_Pnt, gp_Dir, gp_Ax3, gp_Quaternion, gp_Mat

class Step6DofExtractor:
    def __init__(self, stp_path):
        self.stp_path = stp_path
        self.id_to_data = {} # Map ID -> Raw STEP line data
        self.id_to_entity = {} # Map ID -> Specific data object
        self._load_step_raw()

    def _load_step_raw(self):
        """實作快速正則解析，直接從 STEP 提取內容避免 OCC 慢速載入"""
        try:
            with open(self.stp_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                data_sec = re.search(r'DATA;\s*(.*?)\s*ENDSEC;', content, re.DOTALL | re.IGNORECASE)
                if data_sec:
                    # 匹配 #ID = TYPE(ARGS);
                    pattern = re.compile(r'#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*?)\)\s*;', re.DOTALL)
                    for match in pattern.finditer(data_sec.group(1)):
                        eid, etype, eargs = match.groups()
                        self.id_to_data[eid] = {'type': etype, 'args': eargs}
        except Exception as e:
            print(f"Error loading STEP: {e}")

    def _get_coords(self, eid):
        """提取 CARTESIAN_POINT 或 DIRECTION 的數值"""
        item = self.id_to_data.get(str(eid))
        if not item: return None
        # 匹配 (0.0, 1.0, 2.0)
        m = re.search(r'\(([^()]*)\)', item['args'])
        if m:
            try:
                return [float(x.strip()) for x in m.group(1).split(',')]
            except: return None
        return None

    def get_axis2_placement(self, eid):
        """解析 AXIS2_PLACEMENT_3D 轉換為 gp_Trsf"""
        item = self.id_to_data.get(str(eid))
        if not item or item['type'] != 'AXIS2_PLACEMENT_3D':
            return None

        # Args: ('', #Location, #Axis, #Ref_Direction)
        args = [x.strip().replace('#','') for x in item['args'].split(',')]
        if len(args) < 2: return None

        loc_id = args[1]
        axis_id = args[2] if len(args) > 2 and args[2] != '*' else None
        ref_id = args[3] if len(args) > 3 and args[3] != '*' else None

        loc = self._get_coords(loc_id)
        if not loc: return None

        # Default Axis: (0,0,1), Default Ref: (1,0,0)
        z_vec = self._get_coords(axis_id) if axis_id else [0,0,1]
        x_vec = self._get_coords(ref_id) if ref_id else [1,0,0]

        try:
            pnt = gp_Pnt(loc[0], loc[1], loc[2])
            z_dir = gp_Dir(z_vec[0], z_vec[1], z_vec[2])
            x_dir = gp_Dir(x_vec[0], x_vec[1], x_vec[2])
            # gp_Ax3(Point, ZDir, XDir)
            ax3 = gp_Ax3(pnt, z_dir, x_dir)
            trsf = gp_Trsf()
            trsf.SetTransformation(ax3)
            return trsf
        except:
            return None

    def calculate_relative_6dof(self, ref_id, target_id):
        """計算兩個座標系之間的 6-DOF 參數 (度數)"""
        t_ref = self.get_axis2_placement(ref_id)
        t_tar = self.get_axis2_placement(target_id)

        if not t_ref or not t_tar:
            return None

        # 相對變換: Target = Ref * Rel -> Rel = Ref^-1 * Target
        rel_trsf = t_ref.Inverted().Multiplied(t_tar)

        # 提取位移 (mm)
        tp = rel_trsf.TranslationPart()
        tra = (round(tp.X(), 6), round(tp.Y(), 6), round(tp.Z(), 6))

        # 提取旋轉 (XYZ Euler Angles in Degrees)
        rot = rel_trsf.GetRotation() # Quaternion
        # 我們將使用傳統 XYZ 順序分解
        mat = rel_trsf.HVectorialPart()

        # 手動從旋轉矩陣計算 Euler 角 (順序: X, Y, Z)
        # r11 r12 r13
        # r21 r22 r23
        # r31 r32 r33
        r11 = mat.Value(1,1); r12 = mat.Value(1,2); r13 = mat.Value(1,3)
        r21 = mat.Value(2,1); r22 = mat.Value(2,2); r23 = mat.Value(2,3)
        r31 = mat.Value(3,1); r32 = mat.Value(3,2); r33 = mat.Value(3,3)

        # Y = asin(r13)
        # X = atan2(-r23, r33)
        # Z = atan2(-r12, r11)
        # 注意: 不同軟體定義順序不同，此處採用常用的 XYZ 內旋 (Intrinsic)
        try:
            sy = r13
            if sy < 1:
                if sy > -1:
                    y = math.asin(sy)
                    x = math.atan2(-r23, r33)
                    z = math.atan2(-r12, r11)
                else: # sy = -1
                    y = -math.pi/2
                    x = -math.atan2(r21, r22)
                    z = 0
            else: # sy = 1
                y = math.pi/2
                x = math.atan2(r21, r22)
                z = 0

            # 轉換為度數
            deg = [round(math.degrees(v), 4) for v in [x, y, z]]
        except:
            deg = [0, 0, 0]

        return {
            'traX': tra[0], 'traY': tra[1], 'traZ': tra[2],
            'rotX': deg[0], 'rotY': deg[1], 'rotZ': deg[2],
            'unit': 'degrees'
        }

if __name__ == "__main__":
    # 測試程式碼
    if len(sys.argv) > 3:
        stp, id1, id2 = sys.argv[1:4]
        ext = Step6DofExtractor(stp)
        res = ext.calculate_relative_6dof(id1, id2)
        print(f"6-DOF Result for #{id1} -> #{id2}:")
        print(res)
