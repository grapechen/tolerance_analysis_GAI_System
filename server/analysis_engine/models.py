# -*- coding: utf-8 -*-
"""
ParameterizationModel — 以 SymPy 符號運算建構 4x4 齊次座標轉換矩陣。
移植自 單機版/ToleranceAnalysis/ToleranceModel.py (ParameterizationModel class)。
已移除所有 GUI/Excel 相依。
"""
from math import pi
from numpy import array
import sympy as sp


class ParameterizationModel:
    # ─── 空間平移 (Spatial Translation) ─────────────────────────────────────
    def translateX(traX, matrix):
        m = array([[1, 0, 0, traX], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def translateY(traY, matrix):
        m = array([[1, 0, 0, 0], [0, 1, 0, traY], [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def translateZ(traZ, matrix):
        m = array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, traZ], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 空間旋轉 (Spatial Rotation) ─────────────────────────────────────────
    def rotationX(rotX, matrix):
        X = rotX * pi / 180
        m = array([[1, 0, 0, 0], [0, sp.cos(X), -sp.sin(X), 0],
                   [0, sp.sin(X), sp.cos(X), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def rotationY(rotY, matrix):
        Y = rotY * pi / 180
        m = array([[sp.cos(Y), 0, sp.sin(Y), 0], [0, 1, 0, 0],
                   [-sp.sin(Y), 0, sp.cos(Y), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def rotationZ(rotZ, matrix):
        Z = rotZ * pi / 180
        m = array([[sp.cos(Z), -sp.sin(Z), 0, 0], [sp.sin(Z), sp.cos(Z), 0, 0],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 距離公差 (Distance Tolerance) ────────────────────────────────────────
    def distanceX(disX, matrix):
        m = array([[1, 0, 0, disX], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def distanceY(disY, matrix):
        m = array([[1, 0, 0, 0], [0, 1, 0, disY], [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def distanceZ(disZ, matrix):
        m = array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, disZ], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 平面度 (Flatness) ────────────────────────────────────────────────────
    def flatnessX(flaX, matrix):
        m = array([[1, 0, 0, flaX], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def flatnessY(flaY, matrix):
        m = array([[1, 0, 0, 0], [0, 1, 0, flaY], [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def flatnessZ(flaZ, matrix):
        m = array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, flaZ], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 對稱度 (Symmetry) ────────────────────────────────────────────────────
    def symmetryX(symX, matrix):
        m = array([[1, 0, 0, symX], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def symmetryY(symY, matrix):
        m = array([[1, 0, 0, 0], [0, 1, 0, symY], [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def symmetryZ(symZ, matrix):
        m = array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, symZ], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 角度公差 (Angularity) ────────────────────────────────────────────────
    def angularity(ang, matrix, zyzang):
        c = zyzang * pi / 180
        mY = array([[sp.cos(ang), 0, sp.sin(ang), 0], [0, 1, 0, 0],
                    [-sp.sin(ang), 0, sp.cos(ang), 0], [0, 0, 0, 1]])
        mZ  = array([[sp.cos(c), -sp.sin(c), 0, 0], [sp.sin(c), sp.cos(c), 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])
        mZ1 = array([[sp.cos(-c), -sp.sin(-c), 0, 0], [sp.sin(-c), sp.cos(-c), 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(mZ.dot(mY).dot(mZ1))

    def angularityX(angX, matrix):
        m = array([[1, 0, 0, 0], [0, sp.cos(angX), -sp.sin(angX), 0],
                   [0, sp.sin(angX), sp.cos(angX), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def angularityY(angY, matrix):
        m = array([[sp.cos(angY), 0, sp.sin(angY), 0], [0, 1, 0, 0],
                   [-sp.sin(angY), 0, sp.cos(angY), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def angularityZ(angZ, matrix):
        m = array([[sp.cos(angZ), -sp.sin(angZ), 0, 0], [sp.sin(angZ), sp.cos(angZ), 0, 0],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 垂直度 (Perpendicularity) ────────────────────────────────────────────
    def perpendicularity(per, matrix, zyzang):
        c = zyzang * pi / 180
        mY = array([[sp.cos(per), 0, sp.sin(per), 0], [0, 1, 0, 0],
                    [-sp.sin(per), 0, sp.cos(per), 0], [0, 0, 0, 1]])
        mZ  = array([[sp.cos(c), -sp.sin(c), 0, 0], [sp.sin(c), sp.cos(c), 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])
        mZ1 = array([[sp.cos(-c), -sp.sin(-c), 0, 0], [sp.sin(-c), sp.cos(-c), 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(mZ.dot(mY).dot(mZ1))

    def perpendicularityX(perX, matrix):
        m = array([[1, 0, 0, 0], [0, sp.cos(perX), -sp.sin(perX), 0],
                   [0, sp.sin(perX), sp.cos(perX), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def perpendicularityY(perY, matrix):
        m = array([[sp.cos(perY), 0, sp.sin(perY), 0], [0, 1, 0, 0],
                   [-sp.sin(perY), 0, sp.cos(perY), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def perpendicularityZ(perZ, matrix):
        m = array([[sp.cos(perZ), -sp.sin(perZ), 0, 0], [sp.sin(perZ), sp.cos(perZ), 0, 0],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 平行度 (Parallelism) ─────────────────────────────────────────────────
    def parallelism(par, matrix, zyzang):
        c = zyzang * pi / 180
        mY = array([[sp.cos(par), 0, sp.sin(par), 0], [0, 1, 0, 0],
                    [-sp.sin(par), 0, sp.cos(par), 0], [0, 0, 0, 1]])
        mZ  = array([[sp.cos(c), -sp.sin(c), 0, 0], [sp.sin(c), sp.cos(c), 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])
        mZ1 = array([[sp.cos(-c), -sp.sin(-c), 0, 0], [sp.sin(-c), sp.cos(-c), 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(mZ.dot(mY).dot(mZ1))

    def parallelismX(parX, matrix):
        m = array([[1, 0, 0, 0], [0, sp.cos(parX), -sp.sin(parX), 0],
                   [0, sp.sin(parX), sp.cos(parX), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def parallelismY(parY, matrix):
        m = array([[sp.cos(parY), 0, sp.sin(parY), 0], [0, 1, 0, 0],
                   [-sp.sin(parY), 0, sp.cos(parY), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def parallelismZ(parZ, matrix):
        m = array([[sp.cos(parZ), -sp.sin(parZ), 0, 0], [sp.sin(parZ), sp.cos(parZ), 0, 0],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 圓跳動-軸向 (Circular Runout Axial) ──────────────────────────────────
    def CircularRunoutAxial(cra, matrix, zyzang):
        c = zyzang * pi / 180
        mY = array([[sp.cos(cra), 0, sp.sin(cra), 0], [0, 1, 0, 0],
                    [-sp.sin(cra), 0, sp.cos(cra), 0], [0, 0, 0, 1]])
        mZ  = array([[sp.cos(c), -sp.sin(c), 0, 0], [sp.sin(c), sp.cos(c), 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])
        mZ1 = array([[sp.cos(-c), -sp.sin(-c), 0, 0], [sp.sin(-c), sp.cos(-c), 0, 0],
                     [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(mZ.dot(mY).dot(mZ1))

    def CircularRunoutAxialX(craX, matrix):
        m = array([[1, 0, 0, 0], [0, sp.cos(craX), -sp.sin(craX), 0],
                   [0, sp.sin(craX), sp.cos(craX), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def CircularRunoutAxialY(craY, matrix):
        m = array([[sp.cos(craY), 0, sp.sin(craY), 0], [0, 1, 0, 0],
                   [-sp.sin(craY), 0, sp.cos(craY), 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def CircularRunoutAxialZ(craZ, matrix):
        m = array([[sp.cos(craZ), -sp.sin(craZ), 0, 0], [sp.sin(craZ), sp.cos(craZ), 0, 0],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 同心度/真圓度/圓柱度/位置度/真直度 ──────────────────────────────────
    def concentricity(con, matrix, zyzang):
        c = zyzang * pi / 180
        m = array([[1, 0, 0, con / 2 * sp.cos(c)], [0, 1, 0, con / 2 * sp.sin(c)],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def circularity(cir, matrix, zyzang):
        c = zyzang * pi / 180
        m = array([[1, 0, 0, cir / 2 * sp.cos(c)], [0, 1, 0, cir / 2 * sp.sin(c)],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def cylindricity(cy, matrix, zyzang):
        c = zyzang * pi / 180
        m = array([[1, 0, 0, cy / 2 * sp.cos(c)], [0, 1, 0, cy / 2 * sp.sin(c)],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def position(pos, matrix, zyzang):
        c = zyzang * pi / 180
        m = array([[1, 0, 0, pos / 2 * sp.cos(c)], [0, 1, 0, pos / 2 * sp.sin(c)],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def Straightness(stra, matrix, zyzang):
        c = zyzang * pi / 180
        m = array([[1, 0, 0, stra / 2 * sp.cos(c)], [0, 1, 0, stra / 2 * sp.sin(c)],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    # ─── 直徑/半徑/圓跳動-直徑 ───────────────────────────────────────────────
    def DiameterTolerance(dia, matrix, zyzang):
        c = zyzang * pi / 180
        m = array([[1, 0, 0, dia * sp.cos(c)], [0, 1, 0, dia * sp.sin(c)],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def RadiuTolerance(rad, matrix, zyzang):
        c = zyzang * pi / 180
        m = array([[1, 0, 0, rad * sp.cos(c)], [0, 1, 0, rad * sp.sin(c)],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)

    def CircularRunoutDiameter(crd, matrix, zyzang):
        c = zyzang * pi / 180
        m = array([[1, 0, 0, crd * sp.cos(c)], [0, 1, 0, crd * sp.sin(c)],
                   [0, 0, 1, 0], [0, 0, 0, 1]])
        return matrix.dot(m)
