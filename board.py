"""
board.py
Cmput 455 sample code
Written by Cmput 455 TA and Martin Mueller

Implements a basic Go board with functions to:
- initialize to a given board size
- check if a move is legal
- play a move

The board uses a 1-dimensional representation with padding
"""

import numpy as np
from typing import List, Tuple
import time
import gtp_connection

from board_base import (
    board_array_size,
    coord_to_point,
    is_black_white,
    is_black_white_empty,
    opponent,
    where1d,
    BLACK,
    WHITE,
    EMPTY,
    BORDER,
    MAXSIZE,
    NO_POINT,
    PASS,
    GO_COLOR,
    GO_POINT,
)


"""
The GoBoard class implements a board and basic functions to play
moves, check the end of the game, and count the acore at the end.
The class also contains basic utility functions for writing a Go player.
For many more utility functions, see the GoBoardUtil class in board_util.py.

The board is stored as a one-dimensional array of GO_POINT in self.board.
See coord_to_point for explanations of the array encoding.
"""
class GoBoard(object):
    def __init__(self, size: int) -> None:
        """
        Creates a Go board of given size
        """
        assert 2 <= size <= MAXSIZE
        self.reset(size)
        self.calculate_rows_cols_diags()
        

    def add_two_captures(self, color: GO_COLOR) -> None:
        if color == BLACK:
            self.black_captures += 2
        elif color == WHITE:
            self.white_captures += 2
    def get_captures(self, color: GO_COLOR) -> None:
        if color == BLACK:
            return self.black_captures
        elif color == WHITE:
            return self.white_captures
    

    def copy(self) -> 'GoBoard':
        b = GoBoard(self.size)
        assert b.NS == self.NS
        assert b.WE == self.WE
        b.ko_recapture = self.ko_recapture
        b.last_move = self.last_move
        b.last2_move = self.last2_move
        b.current_player = self.current_player
        assert b.maxpoint == self.maxpoint
        b.board = np.copy(self.board)
        return b
    
    def calculate_rows_cols_diags(self) -> None:
        if self.size < 5:
            return
        # precalculate all rows, cols, and diags for 5-in-a-row detection
        self.rows = []
        self.cols = []
        for i in range(1, self.size + 1):
            current_row = []
            start = self.row_start(i)
            for pt in range(start, start + self.size):
                current_row.append(pt)
            self.rows.append(current_row)
            
            start = self.row_start(1) + i - 1
            current_col = []
            for pt in range(start, self.row_start(self.size) + i, self.NS):
                current_col.append(pt)
            self.cols.append(current_col)
        
        self.diags = []
        # diag towards SE, starting from first row (1,1) moving right to (1,n)
        start = self.row_start(1)
        for i in range(start, start + self.size):
            diag_SE = []
            pt = i
            while self.get_color(pt) == EMPTY:
                diag_SE.append(pt)
                pt += self.NS + 1
            if len(diag_SE) >= 5:
                self.diags.append(diag_SE)
        # diag towards SE and NE, starting from (2,1) downwards to (n,1)
        for i in range(start + self.NS, self.row_start(self.size) + 1, self.NS):
            diag_SE = []
            diag_NE = []
            pt = i
            while self.get_color(pt) == EMPTY:
                diag_SE.append(pt)
                pt += self.NS + 1
            pt = i
            while self.get_color(pt) == EMPTY:
                diag_NE.append(pt)
                pt += -1 * self.NS + 1
            if len(diag_SE) >= 5:
                self.diags.append(diag_SE)
            if len(diag_NE) >= 5:
                self.diags.append(diag_NE)
        # diag towards NE, starting from (n,2) moving right to (n,n)
        start = self.row_start(self.size) + 1
        for i in range(start, start + self.size):
            diag_NE = []
            pt = i
            while self.get_color(pt) == EMPTY:
                diag_NE.append(pt)
                pt += -1 * self.NS + 1
            if len(diag_NE) >=5:
                self.diags.append(diag_NE)
        assert len(self.rows) == self.size
        assert len(self.cols) == self.size
        assert len(self.diags) == (2 * (self.size - 5) + 1) * 2

    def reset(self, size: int) -> None:
        """
        Creates a start state, an empty board with given size.
        """
        self.size: int = size
        self.NS: int = size + 1
        self.WE: int = 1
        self.ko_recapture: GO_POINT = NO_POINT
        self.last_move: GO_POINT = NO_POINT
        self.last2_move: GO_POINT = NO_POINT
        self.current_player: GO_COLOR = BLACK
        self.maxpoint: int = board_array_size(size)
        self.board: np.ndarray[GO_POINT] = np.full(self.maxpoint, BORDER, dtype=GO_POINT)
        self._initialize_empty_points(self.board)
        self.calculate_rows_cols_diags()
        self.black_captures = 0
        self.white_captures = 0
    
    def get_color(self, point: GO_POINT) -> GO_COLOR:
        return self.board[point]

    def pt(self, row: int, col: int) -> GO_POINT:
        return coord_to_point(row, col, self.size)
  
    def end_of_game(self) -> bool:
        return self.last_move == PASS \
           and self.last2_move == PASS

    # this is equivalent to generating all legal moves
    def get_empty_points(self) -> np.ndarray:
        """
        Return:
            The empty points on the board
        """
        return where1d(self.board == EMPTY)

    def row_start(self, row: int) -> int:
        assert row >= 1
        assert row <= self.size
        return row * self.NS + 1

    def _initialize_empty_points(self, board_array: np.ndarray) -> None:
        """
        Fills points on the board with EMPTY
        Argument
        ---------
        board: numpy array, filled with BORDER
        """
        for row in range(1, self.size + 1):
            start: int = self.row_start(row)
            board_array[start : start + self.size] = EMPTY


    def _is_surrounded(self, point: GO_POINT, color: GO_COLOR) -> bool:
        """
        check whether empty point is surrounded by stones of color
        (or BORDER) neighbors
        """
        for nb in self._neighbors(point):
            nb_color = self.board[nb]
            if nb_color != BORDER and nb_color != color:
                return False
        return True


    def _block_of(self, stone: GO_POINT) -> np.ndarray:
        """
        Find the block of given stone
        Returns a board of boolean markers which are set for
        all the points in the block 
        """
        color: GO_COLOR = self.get_color(stone)
        assert is_black_white(color)
        return self.connected_component(stone)

    def connected_component(self, point: GO_POINT) -> np.ndarray:
        """
        Find the connected component of the given point.
        """
        marker = np.full(self.maxpoint, False, dtype=np.bool_)
        pointstack = [point]
        color: GO_COLOR = self.get_color(point)
        assert is_black_white_empty(color)
        marker[point] = True
        while pointstack:
            p = pointstack.pop()
            neighbors = self.neighbors_of_color(p, color)
            for nb in neighbors:
                if not marker[nb]:
                    marker[nb] = True
                    pointstack.append(nb)
        return marker

    def _detect_and_process_capture(self, nb_point: GO_POINT) -> GO_POINT:
        """
        Check whether opponent block on nb_point is captured.
        If yes, remove the stones.
        Returns the stone if only a single stone was captured,
        and returns NO_POINT otherwise.
        This result is used in play_move to check for possible ko
        """
        single_capture: GO_POINT = NO_POINT
        opp_block = self._block_of(nb_point)
        if not self._has_liberty(opp_block):
            captures = list(where1d(opp_block))
            self.board[captures] = EMPTY
            if len(captures) == 1:
                single_capture = nb_point
        return single_capture
    
    def play_move(self, point: GO_POINT, color: GO_COLOR):
        """
        Tries to play a move of color on the point.
        """
        if self.board[point] != EMPTY:
            return False
        self.board[point] = color
        self.current_player = opponent(color)
        self.last2_move = self.last_move
        self.last_move = point

        O = opponent(color)
        offsets = [1, -1, self.NS, -self.NS, self.NS+1, -(self.NS+1), self.NS-1, -self.NS+1]
        for offset in offsets:
            try:
                if self.board[point+offset] == O and self.board[point+(offset*2)] == O and self.board[point+(offset*3)] == color:
                    self.board[point+offset] = EMPTY
                    self.board[point+(offset*2)] = EMPTY
                    if color == BLACK:
                        self.black_captures += 2
                    else:
                        self.white_captures += 2
            except:
                pass
        return True
    
    
    def isGameOver(self):
        return self.end_of_game() or self.detect_five_in_a_row() != EMPTY or self.boardIsFull() or self.black_captures >= 10 or self.white_captures >= 10
    
    def boardIsFull(self):
        return not EMPTY in self.board

    def index_to_position(self, index: int) -> str:
        """
        Convert a 1D array index to a string representation of the corresponding board position.
        Example: index_to_position(0, 19) returns 'a19', index_to_position(18, 19) returns 's19'
        """
        row = self.size+1 - index // (self.size+1)
        col = chr(ord('a') + index % (self.size+1))
        return col + str(row)
    
    def call_alphabeta(self, color):
        global timelimit_start
        timelimit_start = time.time()          
        

        alpha = -10000
        beta = 10000
        max_result = -10000
        maximizing_move = NO_POINT
        time_out = NO_POINT

        #captureCount = self.getCaptureCount()
        #print(self.get_twoD_board())
        for move in self.get_empty_points():
            #print(format_point(point_to_coord(move, self.size)))
            board_copy = self.copy()
            board_copy.play_move(move, color)
            try:
                move_result = - board_copy.alphabeta(opponent(color), alpha, beta)
            except:
                return 'unknown', NO_POINT
            if move_result > max_result:
                max_result = move_result
                maximizing_move = move

        if max_result >= 1:
            return color, maximizing_move
        elif max_result == 0:
            return 'Draw', maximizing_move
        else:
            return opponent(color), maximizing_move
 
    
    def alphabeta(self, color, alpha, beta):
        if time.time() - timelimit_start > gtp_connection.timelimit:
            raise Exception('timeout')
        
        if self.isGameOver():
            #print("game over")
            #print(self.get_twoD_board())
            value = self.evalEndState(color)
            #print(value)
            return value
        m = alpha
        legal_moves = self.get_empty_points()
        
        black_capture_count, white_capture_count = self.black_captures, self.white_captures
        
        for point in legal_moves:
            
            #print(point)
            board_copy = np.copy(self.board)
            self.play_move(point, color)
            value = - self.alphabeta(opponent(color), -beta, -alpha)

            self.board = board_copy
            self.black_captures, self.white_captures = black_capture_count, white_capture_count
            self.current_player = color

            if value > m:
                m = value
            if m >= beta: 
                return m  # or value in failsoft (later)
            alpha = max(alpha, m)
        return m
    

    def undoMove(self, color, move, captureCount, black_captured, white_captured):
        self.board[move] = EMPTY
        self.black_captures, self.white_captures = captureCount[0], captureCount[1]
        if color == BLACK:
            for point in white_captured:
                self.board[point] = WHITE
        else:
            for point in black_captured:
                self.board[point] = BLACK
        self.current_player = color

    def evalEndState(self, color):
        #print(color)
        if self.detect_five_in_a_row() == color:
            return 1
        elif self.detect_five_in_a_row() == opponent(color):
            return -1
        elif color == BLACK:
            if self.black_captures >=10:
                return 1
            elif self.white_captures >=10:
                return -1
        elif color == WHITE:
            if self.white_captures >=10:
                return 1
            elif self.black_captures >=10:
                return -1
        return 0

    def neighbors_of_color(self, point: GO_POINT, color: GO_COLOR) -> List:
        """ List of neighbors of point of given color """
        nbc: List[GO_POINT] = []
        for nb in self._neighbors(point):
            if self.get_color(nb) == color:
                nbc.append(nb)
        return nbc

    def _neighbors(self, point: GO_POINT) -> List:
        """ List of all four neighbors of the point """
        return [point - 1, point + 1, point - self.NS, point + self.NS]

    def _diag_neighbors(self, point: GO_POINT) -> List:
        """ List of all four diagonal neighbors of point """
        return [point - self.NS - 1,
                point - self.NS + 1,
                point + self.NS - 1,
                point + self.NS + 1]

    def last_board_moves(self) -> List:
        """
        Get the list of last_move and second last move.
        Only include moves on the board (not NO_POINT, not PASS).
        """
        board_moves: List[GO_POINT] = []
        if self.last_move != NO_POINT and self.last_move != PASS:
            board_moves.append(self.last_move)
        if self.last2_move != NO_POINT and self.last2_move != PASS:
            board_moves.append(self.last2_move)
        return board_moves


    def detect_five_in_a_row(self) -> GO_COLOR:
        """
        Returns BLACK or WHITE if any five in a row is detected for the color
        EMPTY otherwise.
        """
        for r in self.rows:
            result = self.has_five_in_list(r)
            if result != EMPTY:
                return result
        for c in self.cols:
            result = self.has_five_in_list(c)
            if result != EMPTY:
                return result
        for d in self.diags:
            result = self.has_five_in_list(d)
            if result != EMPTY:
                return result
        return EMPTY

    def has_five_in_list(self, list) -> GO_COLOR:
        """
        Returns BLACK or WHITE if any five in a rows exist in the list.
        EMPTY otherwise.
        """
        prev = BORDER
        counter = 1
        for stone in list:
            if self.get_color(stone) == prev:
                counter += 1
            else:
                counter = 1
                prev = self.get_color(stone)
            if counter == 5 and prev != EMPTY:
                return prev
        return EMPTY
    


    def get_twoD_board(self) -> np.ndarray:
        """
        Return: numpy array
        a two dimensional numpy array with the goboard.
        Shows stones and empty points as encoded in board_base.py.
        Result is not padded with BORDER points.
        Rows 1..size of goboard are copied into rows 0..size - 1 of board2d
        Then the board is flipped up-down to be consistent with the
        coordinate system in GoGui (row 1 at the bottom).
        """
        size: int = self.size
        board2d: np.ndarray[GO_POINT] = np.zeros((size, size), dtype=GO_POINT)
        for row in range(size):
            start: int = self.row_start(row + 1)
            board2d[row, :] = self.board[start : start + size]
        board2d = np.flipud(board2d)
        return board2d
    

def point_to_coord(point: GO_POINT, boardsize: int) -> Tuple[int, int]:
    """
    Transform point given as board array index 
    to (row, col) coordinate representation.
    Special case: PASS is transformed to (PASS,PASS)
    """
    if point == PASS:
        return (PASS, PASS)
    else:
        NS = boardsize + 1
        return divmod(point, NS)


def format_point(move: Tuple[int, int]) -> str:
    """
    Return move coordinates as a string such as 'A1', or 'PASS'.
    """
    assert MAXSIZE <= 25
    column_letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    if move[0] == PASS:
        return "PASS"
    row, col = move
    if not 0 <= row < MAXSIZE or not 0 <= col < MAXSIZE:
        raise ValueError
    return column_letters[col - 1] + str(row)